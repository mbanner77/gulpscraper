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
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Any, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from apscheduler.schedulers.asyncio import AsyncIOScheduler

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
    allow_origins=["*"],  # In production, you should specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/137.0.0.0 Safari/537.36"
)

API_RE = re.compile(r"/rest/internal/projects/search", re.I)
PROJ_KEY_CANDIDATES = {"title", "jobTitle"}

# Global variable to store the last scrape time
last_scrape_time = None
is_scraping = False

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
    global is_scraping
    
    if is_scraping:
        print("Scrape already in progress, skipping...")
        return []
    
    is_scraping = True
    print(f"Starting GULP scraper at {datetime.now().isoformat()}")
    
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

        # Save the scraped data
        OUTPUT_JSON.write_text(
            json.dumps(all_projects, indent=2, ensure_ascii=False), 
            encoding="utf-8"
        )
        NETWORK_LOG.write_text("\n".join(network_lines), encoding="utf-8")

        print(f"✓ Scraping completed at {datetime.now().isoformat()}")
        print(f"  → {len(all_projects)} projects saved to {OUTPUT_JSON}")
        
        global last_scrape_time
        last_scrape_time = datetime.now().isoformat()
        
        return all_projects
    
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


class ProjectFilter(BaseModel):
    search: Optional[str] = None
    location: Optional[str] = None
    remote: Optional[bool] = None
    page: int = 1
    limit: int = 10


# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "GULP Job Scraper API",
        "version": "1.0.0",
        "endpoints": [
            {"path": "/", "method": "GET", "description": "This information"},
            {"path": "/projects", "method": "GET", "description": "Get all projects with optional filtering"},
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
):
    """Get all projects with optional filtering and pagination."""
    try:
        if not OUTPUT_JSON.exists():
            # If no data exists yet, run the scraper
            await scrape_gulp()
            
        if not OUTPUT_JSON.exists():
            return JSONResponse(
                status_code=404,
                content={"error": "No project data available. Try triggering a scrape first."}
            )
            
        # Read the projects from the JSON file
        projects = json.loads(OUTPUT_JSON.read_text(encoding="utf-8"))
        
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
        total_pages = (total + limit - 1) // limit
        start_idx = (page - 1) * limit
        end_idx = min(start_idx + limit, total)
        
        return {
            "total": total,
            "page": page,
            "limit": limit,
            "totalPages": total_pages,
            "data": filtered_projects[start_idx:end_idx],
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
    if is_scraping:
        return JSONResponse(
            status_code=409,
            content={"error": "A scrape is already in progress"}
        )
        
    # Convert the pages list to a range if provided
    pages = PAGE_RANGE
    if request.pages:
        pages = range(min(request.pages), max(request.pages) + 1)
        
    # Run the scrape in the background
    background_tasks.add_task(scrape_gulp, pages)
    
    return {"message": "Scrape started in the background"}


@app.get("/status")
async def get_status():
    """Get the scraper status."""
    return {
        "is_scraping": is_scraping,
        "last_scrape": last_scrape_time,
        "data_available": OUTPUT_JSON.exists(),
        "project_count": len(json.loads(OUTPUT_JSON.read_text(encoding="utf-8"))) if OUTPUT_JSON.exists() else 0
    }


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

# Set up the scheduler to run the scraper once a day
scheduler = AsyncIOScheduler()

@scheduler.scheduled_job("cron", hour=3)  # Run at 3 AM every day
async def scheduled_scrape():
    """Run the scraper on a schedule."""
    print(f"Running scheduled scrape at {datetime.now().isoformat()}")
    await scrape_gulp()


# ---------------------------------------------------------------------------
# Startup and Shutdown Events
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup_event():
    """Run when the API starts up."""
    # Start the scheduler
    scheduler.start()
    
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
    uvicorn.run("scraper:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), log_level="info")
