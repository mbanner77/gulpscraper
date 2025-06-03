"""
GULP Job Scraper API - Cloud Version
===================================
Modified version of the original gulp22.py script to work as an API
in a cloud environment. This script will:
1. Run the scraper on a schedule
2. Store the results in a data directory
3. Provide API endpoints to access the data
"""

import asyncio
import json
import re
import os
import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Any, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks, Form, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Importieren der eigenen Module
from email_service import EmailService
from project_manager import ProjectManager

# Import Playwright with proper error handling
try:
    from playwright.async_api import async_playwright, TimeoutError as PwTimeout
except ImportError:
    print("Playwright not installed. Please run: pip install playwright")
    print("And then: playwright install chromium")
    raise

# Initialize FastAPI app
app = FastAPI(
    title="GULP Job Scraper API",
    description="API for scraping and accessing GULP job listings",
    version="1.0.0",
)

# Add CORS middleware to allow requests from the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:8000",
        "https://*.onrender.com",  # Allow all Render subdomains
        "https://*.render.com",    # Allow all Render domains
        os.environ.get("FRONTEND_URL", "*")  # Get from environment or allow all as fallback
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Globale Variablen für Dienste
email_service = None
project_manager = None

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
START_URL_TEMPLATE = "https://www.gulp.de/gulp2/g/projekte?page={page}"
PAGE_RANGE = range(1, 4)  # First 3 pages by default
HEADLESS = True  # Always run headless in cloud environment
TIMEOUT_MS = 45_000
SCROLL_PAUSE = 0.8
SCROLL_STEPS = 6
COLLECT_SECS = 8

# Set up data directory
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
OUTPUT_JSON = DATA_DIR / "gulp_projekte_raw.json"
DEBUG_DIR = DATA_DIR / "debug"
DEBUG_DIR.mkdir(exist_ok=True)
NETWORK_LOG = DEBUG_DIR / "network.log"

# E-Mail-Konfiguration
DEFAULT_EMAIL_RECIPIENT = os.environ.get("EMAIL_RECIPIENT", "")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/137.0.0.0 Safari/537.36"
)

API_RE = re.compile(r"/rest/internal/projects/search", re.I)
PROJ_KEY_CANDIDATES = {"title", "jobTitle"}

# Global variables for scraper state
last_scrape_time = None
is_scraping = False
email_notification_enabled = False
email_recipient = DEFAULT_EMAIL_RECIPIENT

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def find_projects_recursive(data: Any) -> List[Dict]:
    """Recursively collect dicts that look like projects."""
    found = []
    if isinstance(data, list):
        for item in data:
            found.extend(find_projects_recursive(item))
    elif isinstance(data, dict):
        if PROJ_KEY_CANDIDATES.intersection(data.keys()):
            found.append(data)
        for v in data.values():
            found.extend(find_projects_recursive(v))
    return found


async def scrape_gulp(pages: range = PAGE_RANGE) -> List[Dict]:
    """Run the GULP scraper and return the projects."""
    global is_scraping, last_scrape_time, project_manager, email_service, email_notification_enabled, email_recipient
    
    if is_scraping:
        print("Scrape already in progress, skipping...")
        return []
    
    is_scraping = True
    print(f"Starting GULP scraper at {datetime.datetime.now().isoformat()}")
    
    all_projects: List[dict] = []
    network_lines: List[str] = []

    try:
        async with async_playwright() as pw:
            # Launch browser with appropriate options for cloud environment
            browser = await pw.chromium.launch(
                headless=HEADLESS, 
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-accelerated-2d-canvas",
                    "--no-first-run",
                    "--no-zygote",
                    "--single-process",
                    "--disable-gpu"
                ]
            )
            context = await browser.new_context(
                user_agent=USER_AGENT, 
                viewport={"width": 1280, "height": 900}
            )
            page = await context.new_page()

            page.on("response", lambda resp: network_lines.append(
                f"{resp.status} {resp.request.method} {resp.url} [{resp.headers.get('content-type', '')}]"))

            for page_idx in pages:
                print(f"→ Page {page_idx}: {START_URL_TEMPLATE.format(page=page_idx)}")
                captured: List[Tuple[str, Any]] = []

                def handle_response(resp):
                    if API_RE.search(resp.url) and "application/json" in resp.headers.get("content-type", ""):
                        async def _grab():
                            try:
                                captured.append((resp.url, await resp.json()))
                            except Exception:
                                pass
                        asyncio.create_task(_grab())
                page.on("response", handle_response)

                try:
                    await page.goto(
                        START_URL_TEMPLATE.format(page=page_idx), 
                        timeout=TIMEOUT_MS, 
                        wait_until="domcontentloaded"
                    )
                except PwTimeout:
                    print("   ! DOMContentLoaded Timeout – skipping page")
                    continue

                for _ in range(SCROLL_STEPS):
                    await page.mouse.wheel(0, 4000)
                    await asyncio.sleep(SCROLL_PAUSE)
                await asyncio.sleep(COLLECT_SECS)

                if captured:
                    feed_url, api_json = captured[0]
                    (DEBUG_DIR / f"api_page{page_idx}.json").write_text(
                        json.dumps(api_json, indent=2, ensure_ascii=False), 
                        encoding="utf-8"
                    )
                else:
                    feed_url, api_json = "n/a", {}

                projects: List[Dict] = []
                if isinstance(api_json, dict):
                    for key in ("content", "data", "items", "projects", "results"):
                        if isinstance(api_json.get(key), list):
                            projects = api_json[key]
                            break
                if not projects:
                    projects = find_projects_recursive(api_json)

                print(f"   {len(projects)} projects found (source: {feed_url})")
                all_projects.extend(projects)

            await page.close()
            await context.close()
            await browser.close()

        # Verarbeite die gescrapten Projekte (Duplikaterkennung und neue Projekte identifizieren)
        unique_projects, new_projects = project_manager.process_projects(all_projects)
        
        # Speichere die eindeutigen Projekte
        OUTPUT_JSON.write_text(
            json.dumps(unique_projects, indent=2, ensure_ascii=False), 
            encoding="utf-8"
        )
        NETWORK_LOG.write_text("\n".join(network_lines), encoding="utf-8")

        print(f"✓ Scraping completed at {datetime.datetime.now().isoformat()}")
        print(f"  → {len(unique_projects)} unique projects saved to {OUTPUT_JSON}")
        print(f"  → {len(new_projects)} new projects found")
        
        # Aktualisiere den Zeitstempel des letzten Scans
        last_scrape_time = datetime.datetime.now().isoformat()
        
        # Sende E-Mail-Benachrichtigung, wenn aktiviert und neue Projekte gefunden wurden
        if email_notification_enabled and email_recipient and new_projects and email_service:
            try:
                email_service.send_new_projects_notification(
                    recipient=email_recipient,
                    new_projects=new_projects,
                    scan_time=datetime.datetime.now()
                )
            except Exception as e:
                print(f"Error sending email notification: {str(e)}")
        
        return unique_projects
    
    except Exception as e:
        print(f"Error during scraping: {str(e)}")
        return []
    
    finally:
        is_scraping = False


# ---------------------------------------------------------------------------
# API Models
# ---------------------------------------------------------------------------

class ScrapeRequest(BaseModel):
    pages: Optional[List[int]] = None
    send_email: bool = False


class ProjectFilter(BaseModel):
    search: Optional[str] = None
    location: Optional[str] = None
    remote: Optional[bool] = None
    page: int = 1
    limit: int = 10
    include_new_only: bool = False


class EmailConfig(BaseModel):
    smtp_host: str
    smtp_port: int = 587
    smtp_user: str
    smtp_password: str
    sender: Optional[str] = None
    recipient: EmailStr
    enabled: bool = True
    frontend_url: Optional[str] = None


class SchedulerConfig(BaseModel):
    enabled: bool = True
    interval_days: int = 1  # Default: run every day
    daily_runs: List[Dict[str, int]] = [
        {"hour": 3, "minute": 0}  # Default: run once at 3 AM
    ]


# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------

# Scheduler configuration endpoints
@app.get("/scheduler-config")
async def get_scheduler_config():
    """Get the current scheduler configuration."""
    jobs_info = []
    for job in scheduler.get_jobs():
        try:
            next_run = job.next_run_time.isoformat() if job.next_run_time else None
            jobs_info.append({
                "id": job.id,
                "next_run_time": next_run,
                "trigger": str(job.trigger),
                "function": job.func.__name__ if hasattr(job.func, "__name__") else str(job.func)
            })
        except Exception as e:
            jobs_info.append({
                "id": job.id,
                "error": str(e)
            })
    
    return {
        "config": scheduler_config,
        "jobs": jobs_info,
        "scheduler_running": scheduler.running,
        "scheduler_state": {
            "running": scheduler.running,
            "state": scheduler.state if hasattr(scheduler, "state") else "unknown",
            "job_count": len(scheduler.get_jobs())
        }
    }

@app.post("/restart-scheduler")
async def restart_scheduler():
    """Force restart the scheduler to ensure jobs are properly registered."""
    global scheduler
    try:
        # Stop the scheduler if it's running
        if scheduler.running:
            try:
                scheduler.shutdown(wait=False)
                print("Scheduler shutdown successfully")
            except Exception as shutdown_error:
                print(f"Error shutting down scheduler: {str(shutdown_error)}")
        
        # Configure the scheduler with current settings
        configure_scheduler()
        
        # Start the scheduler
        try:
            scheduler.start()
            print("Scheduler started successfully")
        except Exception as start_error:
            print(f"Error starting scheduler: {str(start_error)}")
            # Try to create a new scheduler instance if starting fails
            scheduler = AsyncIOScheduler()
            configure_scheduler()
            scheduler.start()
        
        # Get current jobs
        jobs = []
        for job in scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger)
            })
        
        return {
            "message": "Scheduler restarted successfully",
            "jobs": jobs,
            "scheduler_running": scheduler.running,
            "config": scheduler_config
        }
    except Exception as e:
        print(f"Error in restart_scheduler: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Error restarting scheduler: {str(e)}"}
        )

@app.post("/scheduler-config")
async def set_scheduler_config(config: SchedulerConfig):
    """Update the scheduler configuration."""
    global scheduler_config
    
    try:
        # Validate interval days
        if config.interval_days < 1 or config.interval_days > 30:
            return JSONResponse(
                status_code=400,
                content={"error": "Interval days must be between 1 and 30"}
            )
        
        # Validate daily runs
        if not config.daily_runs:
            return JSONResponse(
                status_code=400,
                content={"error": "At least one daily run must be specified"}
            )
        
        # Validate each run time
        for run in config.daily_runs:
            if "hour" not in run or "minute" not in run:
                return JSONResponse(
                    status_code=400,
                    content={"error": "Each run must specify hour and minute"}
                )
            
            if run["hour"] < 0 or run["hour"] > 23:
                return JSONResponse(
                    status_code=400,
                    content={"error": "Hour must be between 0 and 23"}
                )
                
            if run["minute"] < 0 or run["minute"] > 59:
                return JSONResponse(
                    status_code=400,
                    content={"error": "Minute must be between 0 and 59"}
                )
        
        # Update configuration
        scheduler_config["enabled"] = config.enabled
        scheduler_config["interval_days"] = config.interval_days
        scheduler_config["daily_runs"] = config.daily_runs
        
        # Reconfigure the scheduler
        configure_scheduler()
        
        return {
            "message": "Scheduler configuration updated successfully",
            "config": scheduler_config
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Error updating scheduler configuration: {str(e)}"}
        )

@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "GULP Job Scraper API",
        "version": "1.0.0",
        "endpoints": [
            {"path": "/", "method": "GET", "description": "This information"},
            {"path": "/projects", "method": "GET", "description": "Get recent projects (last 24h) with optional filtering"},
            {"path": "/projects/archive", "method": "GET", "description": "Get archived projects (older than 24h) with optional filtering"},
            {"path": "/projects/{id}", "method": "GET", "description": "Get a specific project by ID"},
            {"path": "/scrape", "method": "POST", "description": "Trigger a new scrape (admin only)"},
            {"path": "/status", "method": "GET", "description": "Get the scraper status"},
        ],
    }


@app.get("/projects")
async def get_projects(
    search: Optional[str] = None,
    location: Optional[str] = None,
    remote: Optional[bool] = None,
    page: int = 1,
    limit: int = 10,
    include_new_only: bool = False,
):
    """Get recent projects (last 24h) with optional filtering and pagination."""
    try:
        if not OUTPUT_JSON.exists():
            # If no data exists yet, run the scraper
            await scrape_gulp()
            
        if not OUTPUT_JSON.exists():
            return JSONResponse(
                status_code=404,
                content={"error": "No project data available. Try triggering a scrape first."}
            )
        
        # Get projects from the project manager
        if include_new_only:
            # Get only new projects
            projects, total = project_manager.get_projects(
                search=search, 
                location=location, 
                remote=remote, 
                page=page, 
                limit=limit, 
                include_new_only=True,
                archived=False
            )
        else:
            # Get recent projects (last 24h)
            projects, total = project_manager.get_projects(
                search=search, 
                location=location, 
                remote=remote, 
                page=page, 
                limit=limit, 
                include_new_only=False,
                archived=False
            )
        
        # Apply filters
        filtered_projects = projects
        
        if search:
            search_lower = search.lower()
            filtered_projects = [
                p for p in filtered_projects if
                (p.get("title", "").lower().find(search_lower) >= 0 or
                 p.get("description", "").lower().find(search_lower) >= 0 or
                 p.get("companyName", "").lower().find(search_lower) >= 0)
            ]
            
        if location:
            location_lower = location.lower()
            filtered_projects = [
                p for p in filtered_projects if
                p.get("location", "").lower().find(location_lower) >= 0
            ]
            
        if remote is not None:
            filtered_projects = [
                p for p in filtered_projects if
                p.get("isRemoteWorkPossible") == remote
            ]
            
        # Calculate pagination
        total = len(filtered_projects)
        total_pages = (total + limit - 1) // limit if limit > 0 else 1
        start_idx = (page - 1) * limit if limit > 0 else 0
        end_idx = min(start_idx + limit, total) if limit > 0 else total
        
        # Hole die neuen Projekte, um sie im Frontend markieren zu können
        new_project_ids = {p.get("id") for p in project_manager.get_new_projects()}
        
        return {
            "projects": filtered_projects[start_idx:end_idx],
            "total": total,
            "page": page,
            "limit": limit,
            "type": "recent",
            "lastScrape": last_scrape_time,
            "newProjectIds": list(new_project_ids)
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Error retrieving projects: {str(e)}"}
        )


@app.get("/projects/archive")
async def get_archived_projects(
    search: Optional[str] = None,
    location: Optional[str] = None,
    remote: Optional[bool] = None,
    page: int = 1,
    limit: int = 10,
):
    """Get archived projects (older than 24h) with optional filtering and pagination."""
    try:
        # Get archived projects from the project manager
        projects, total = project_manager.get_projects(
            search=search, 
            location=location, 
            remote=remote, 
            page=page, 
            limit=limit, 
            include_new_only=False,
            archived=True
        )
        
        # Calculate pagination
        total_pages = (total + limit - 1) // limit if limit > 0 else 1
        
        return {
            "projects": projects,
            "total": total,
            "page": page,
            "limit": limit,
            "type": "archive",
            "lastScrape": last_scrape_time
        }
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Error retrieving projects: {str(e)}"}
        )


@app.get("/projects/{project_id}")
async def get_project(project_id: str):
    """Get a specific project by ID."""
    try:
        if not OUTPUT_JSON.exists():
            return JSONResponse(
                status_code=404,
                content={"error": "No project data available. Try triggering a scrape first."}
            )
            
        # Read the projects from the JSON file
        projects = json.loads(OUTPUT_JSON.read_text(encoding="utf-8"))
        
        # Find the project with the given ID
        project = next((p for p in projects if p.get("id") == project_id), None)
        
        if not project:
            return JSONResponse(
                status_code=404,
                content={"error": f"Project with ID {project_id} not found"}
            )
            
        return project
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Error retrieving project: {str(e)}"}
        )


@app.post("/scrape")
async def trigger_scrape(
    background_tasks: BackgroundTasks,
    request: ScrapeRequest = ScrapeRequest()
):
    """Trigger a new scrape."""
    global email_notification_enabled
    
    if is_scraping:
        return JSONResponse(
            status_code=409,
            content={"error": "A scrape is already in progress"}
        )
        
    # Convert the pages list to a range if provided
    pages = PAGE_RANGE
    if request.pages:
        pages = range(min(request.pages), max(request.pages) + 1)
    
    # Aktiviere E-Mail-Benachrichtigung für diesen Scrape-Vorgang, wenn angefordert
    if request.send_email:
        email_notification_enabled = True
    else:
        email_notification_enabled = False
        
    # Run the scrape in the background
    background_tasks.add_task(scrape_gulp, pages)
    
    return {
        "message": "Scrape started in the background",
        "email_notification": email_notification_enabled and email_recipient != ""
    }


@app.get("/status")
async def get_status():
    """Get the scraper status."""
    history = project_manager.get_history()
    new_projects = project_manager.get_new_projects()
    
    return {
        "is_scraping": is_scraping,
        "last_scrape": last_scrape_time,
        "data_available": OUTPUT_JSON.exists(),
        "project_count": len(json.loads(OUTPUT_JSON.read_text(encoding="utf-8"))) if OUTPUT_JSON.exists() else 0,
        "new_project_count": len(new_projects),
        "total_projects_found": history.get("total_projects_found", 0),
        "email_notification": {
            "enabled": email_notification_enabled,
            "recipient": email_recipient if email_recipient else None,
            "configured": email_service.is_configured if email_service else False
        },
        "scheduler": {
            "enabled": scheduler_config["enabled"],
            "interval_days": scheduler_config["interval_days"],
            "daily_runs": scheduler_config["daily_runs"]
        },
        "archive": {
            "count": project_manager.get_archive_count()
        }
    }


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

# Default scheduler configuration
scheduler_config = {
    "enabled": True,
    "interval_days": 1,  # Default: run every day
    "daily_runs": [
        {"hour": 3, "minute": 0}  # Default: run once at 3 AM
    ]
}

# Set up the scheduler
scheduler = AsyncIOScheduler()
scheduler_job = None

# Function to configure the scheduler based on settings
def configure_scheduler():
    global scheduler_job
    
    print("\n--- CONFIGURING SCHEDULER ---")
    print(f"Current scheduler state: Running={scheduler.running}")
    print(f"Current jobs before removal: {[job.id for job in scheduler.get_jobs()]}")
    
    # Remove existing jobs
    for job in scheduler.get_jobs():
        try:
            job.remove()
            print(f"Removed job: {job.id}")
        except Exception as e:
            print(f"Error removing job {job.id}: {str(e)}")
    
    if scheduler_config["enabled"]:
        print(f"Scheduler is enabled, configuring {len(scheduler_config['daily_runs'])} daily runs")
        for i, run in enumerate(scheduler_config["daily_runs"]):
            try:
                job = scheduler.add_job(
                    scheduled_scrape,
                    'cron',
                    hour=run["hour"],
                    minute=run["minute"],
                    day=f'*/{scheduler_config["interval_days"]}',
                    id=f'scraper_job_{i}',
                    replace_existing=True
                )
                print(f"Added job {job.id} to run at {run['hour']}:{run['minute']} every {scheduler_config['interval_days']} day(s)")
                print(f"Next run time: {job.next_run_time}")
            except Exception as e:
                print(f"Error adding job for run at {run['hour']}:{run['minute']}: {str(e)}")
        
        print(f"Total scheduled runs: {len(scheduler_config['daily_runs'])}")
        print(f"Jobs after configuration: {[job.id for job in scheduler.get_jobs()]}")
    else:
        print("Scheduler disabled")
    print("--- END SCHEDULER CONFIGURATION ---\n")

async def scheduled_scrape():
    """Run the scraper on a schedule."""
    print(f"Running scheduled scrape at {datetime.datetime.now().isoformat()}")
    await scrape_gulp()


# ---------------------------------------------------------------------------
# Startup and Shutdown Events
# ---------------------------------------------------------------------------

# Neue API-Endpunkte für E-Mail-Konfiguration und neue Projekte

@app.post("/email-config")
async def set_email_config(config: EmailConfig):
    """Konfiguriere den E-Mail-Service."""
    global email_service, email_notification_enabled, email_recipient
    
    try:
        # E-Mail-Service mit neuer Konfiguration erstellen
        email_service = EmailService(
            smtp_host=config.smtp_host,
            smtp_port=config.smtp_port,
            smtp_user=config.smtp_user,
            smtp_password=config.smtp_password,
            sender=config.sender,
            frontend_url=config.frontend_url or FRONTEND_URL
        )
        
        # E-Mail-Benachrichtigung aktivieren/deaktivieren
        email_notification_enabled = config.enabled
        email_recipient = config.recipient
        
        return {
            "message": "E-Mail-Konfiguration erfolgreich gespeichert",
            "is_configured": email_service.is_configured
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Fehler beim Speichern der E-Mail-Konfiguration: {str(e)}"}
        )

@app.get("/email-config")
async def get_email_config():
    """Gibt die aktuelle E-Mail-Konfiguration zurück."""
    if not email_service:
        return {
            "is_configured": False,
            "enabled": email_notification_enabled,
            "recipient": email_recipient
        }
    
    config = email_service.get_config_status()
    config["enabled"] = email_notification_enabled
    config["recipient"] = email_recipient
    
    # Passwort aus Sicherheitsgründen nicht zurückgeben
    if "smtp_password" in config:
        config["smtp_password"] = "********"
    
    return config

@app.get("/new-projects")
async def get_new_projects():
    """Gibt die neuen Projekte zurück."""
    new_projects = project_manager.get_new_projects()
    
    return {
        "count": len(new_projects),
        "data": new_projects
    }

@app.post("/mark-projects-seen")
async def mark_projects_seen(project_ids: List[str]):
    """Markiert Projekte als gesehen (nicht mehr neu)."""
    project_manager.mark_projects_as_seen(project_ids)
    
    return {
        "message": f"{len(project_ids)} Projekte als gesehen markiert",
        "remaining_new": len(project_manager.get_new_projects())
    }

@app.on_event("startup")
async def startup_event():
    """Run when the API starts up."""
    global project_manager, email_service
    
    # Initialisiere den Projekt-Manager
    project_manager = ProjectManager(DATA_DIR)
    
    # Initialisiere den E-Mail-Service mit Umgebungsvariablen
    email_service = EmailService(
        smtp_host=os.environ.get("SMTP_HOST"),
        smtp_port=int(os.environ.get("SMTP_PORT", 587)),
        smtp_user=os.environ.get("SMTP_USER"),
        smtp_password=os.environ.get("SMTP_PASSWORD"),
        sender=os.environ.get("EMAIL_SENDER"),
        frontend_url=FRONTEND_URL
    )
    
    # Configure and start the scheduler
    configure_scheduler()
    
    # Make sure the scheduler is not already running before starting it
    if not scheduler.running:
        try:
            scheduler.start()
            print("Scheduler started successfully")
        except Exception as e:
            print(f"Error starting scheduler: {str(e)}")
    else:
        print("Scheduler is already running")
    
    # Run the scraper on startup if no data exists
    if not OUTPUT_JSON.exists():
        asyncio.create_task(scrape_gulp())


@app.on_event("shutdown")
async def shutdown_event():
    """Run when the API shuts down."""
    # Shut down the scheduler
    scheduler.shutdown()


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Run the API server
    uvicorn.run("scraper:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8001)), log_level="info")
