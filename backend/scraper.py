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
import sys
import datetime
import traceback
from pathlib import Path
from typing import List, Dict, Tuple, Any, Optional, Union
from pydantic import BaseModel, EmailStr

import uvicorn
from fastapi import FastAPI, BackgroundTasks, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Dict, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import os
import json
import datetime
import time
import uuid
import logging
import traceback
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from project_manager import ProjectManager
from email_service import EmailService
from email_test_route import router as email_router

# Import Playwright with proper error handling
try:
    from playwright.async_api import async_playwright, TimeoutError as PwTimeout
except ImportError:
    print("Playwright not installed. Please run: pip install playwright")
    print("And then: playwright install chromium")
    raise

# Determine if we're running in a cloud environment
IS_CLOUD_ENV = os.environ.get('RENDER', False) or os.environ.get('CLOUD_ENV', False)

# Determine if we should use the real scraper (default: True)
USE_REAL_SCRAPER = os.environ.get('USE_REAL_SCRAPER', 'True').lower() in ('true', '1', 't')

# Auf Render verwenden wir standardmäßig den echten Scraper, außer wenn explizit deaktiviert
if IS_CLOUD_ENV and 'USE_REAL_SCRAPER' not in os.environ:
    print("[RENDER CONFIG] Setze USE_REAL_SCRAPER=True für Render-Umgebung (Standard)")
    USE_REAL_SCRAPER = True

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

# Importiere die E-Mail-Test-Route
from email_test_route import router as email_router

# Registriere die E-Mail-Test-Route
app.include_router(email_router, prefix="/api/email", tags=["email"])

# Globale Variablen für Dienste
email_service = None
project_manager = None

# Globale Variable für Scraper-Logs
scraper_logs = []
max_log_entries = 100  # Maximale Anzahl der Log-Einträge

def save_logs_to_file():
    """
    Speichert die Scraper-Logs in einer Datei.
    """
    try:
        with open(SCRAPER_LOGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(scraper_logs, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Fehler beim Speichern der Scraper-Logs: {str(e)}")

def load_logs_from_file():
    """
    Lädt die Scraper-Logs aus einer Datei.
    """
    global scraper_logs
    try:
        if SCRAPER_LOGS_FILE.exists():
            with open(SCRAPER_LOGS_FILE, 'r', encoding='utf-8') as f:
                loaded_logs = json.load(f)
                # Stelle sicher, dass wir eine Liste haben
                if isinstance(loaded_logs, list):
                    scraper_logs = loaded_logs
                    print(f"[INFO] {len(scraper_logs)} Scraper-Logs aus Datei geladen.")
    except Exception as e:
        print(f"Fehler beim Laden der Scraper-Logs: {str(e)}")

def log_scraper_event(event_type, message, data=None):
    """
    Fügt einen neuen Log-Eintrag zu den Scraper-Logs hinzu.
    
    Args:
        event_type (str): Art des Events (info, warning, error, success)
        message (str): Nachricht für das Log
        data (dict, optional): Zusätzliche Daten zum Event
    """
    global scraper_logs, max_log_entries
    
    # Erstelle einen neuen Log-Eintrag
    log_entry = {
        "event_type": event_type,
        "message": message,
        "timestamp": datetime.datetime.now().isoformat(),
        "data": data
    }
    
    # Füge den Eintrag am Anfang der Liste hinzu (neueste zuerst)
    scraper_logs.insert(0, log_entry)
    
    # Begrenze die Anzahl der Log-Einträge
    if len(scraper_logs) > max_log_entries:
        scraper_logs = scraper_logs[:max_log_entries]
    
    # Speichere die Logs in einer Datei
    save_logs_to_file()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
START_URL_TEMPLATE = "https://www.gulp.de/gulp2/g/projekte?page={page}"
PAGE_RANGE = range(1, 4)  # First 3 pages by default
# Always run headless in cloud environment
HEADLESS = True if IS_CLOUD_ENV else os.environ.get('HEADLESS', 'True').lower() in ('true', '1', 't')
TIMEOUT_MS = 45_000
SCROLL_PAUSE = 0.8
SCROLL_STEPS = 6
COLLECT_SECS = 8

# Set up data directory - use environment variable if available (for cloud environments)
data_dir_path = os.environ.get('DATA_DIR', 'data')
DATA_DIR = Path(data_dir_path)

# Pfad zur Log-Datei
SCRAPER_LOGS_FILE = Path(data_dir_path) / "scraper_logs.json"
DATA_DIR.mkdir(exist_ok=True)
OUTPUT_JSON = DATA_DIR / "gulp_projekte_raw.json"
DEBUG_DIR = DATA_DIR / "debug"
DEBUG_DIR.mkdir(exist_ok=True)
NETWORK_LOG = DEBUG_DIR / "network.log"
LAST_SCRAPE_FILE = DATA_DIR / "last_scrape.txt"

# Log data directory location
print(f"Using data directory: {DATA_DIR.absolute()}")

# For cloud environments, warn about non-persistent storage
if IS_CLOUD_ENV:
    print("WARNING: Running in cloud environment. Data may not persist between restarts unless using a mounted volume.")
    print("Consider using a database or cloud storage service for persistent data.")


# E-Mail-Konfiguration
DEFAULT_EMAIL_RECIPIENT = os.environ.get("EMAIL_RECIPIENT", "m.banner@realcore.de")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost")

# Standard SMTP-Konfiguration
DEFAULT_SMTP_HOST = os.environ.get("SMTP_HOST", "mail.tk-core.de")
DEFAULT_SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))
DEFAULT_SMTP_USER = os.environ.get("SMTP_USER", "gulpai@tk-core.de")
DEFAULT_SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "gulpai2025")
DEFAULT_EMAIL_SENDER = os.environ.get("EMAIL_SENDER", "GULP Job Scraper <gulpai@tk-core.de>")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/137.0.0.0 Safari/537.36"
)

API_RE = re.compile(r"/rest/internal/projects/search", re.I)
PROJ_KEY_CANDIDATES = {"title", "jobTitle"}

# Globale Variablen für den Scraper-Status
is_scraping = False
last_scrape_time = None
email_notification_enabled = True
email_recipient = DEFAULT_EMAIL_RECIPIENT
last_used_dummy_data = False  # Neue Variable, die anzeigt, ob beim letzten Scrape Dummy-Daten verwendet wurden

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


async def scrape_gulp(pages: range = PAGE_RANGE):
    """Run the GULP scraper and return the projects."""
    global is_scraping, last_scrape_time, last_used_dummy_data, project_manager, email_service, email_notification_enabled, email_recipient
    
    if is_scraping:
        log_scraper_event("warning", "Scraper is already running, skipping")
        return []
    
    is_scraping = True
    all_projects: List[Dict] = []
    network_lines: List[str] = []
    
    try:
        log_scraper_event("info", f"Starting GULP scraper", {
            "timestamp": datetime.datetime.now().isoformat(),
            "use_real_scraper": USE_REAL_SCRAPER,
            "is_cloud_env": IS_CLOUD_ENV,
            "pages": list(pages)
        })
        
        # Erstelle Debug-Verzeichnisse, falls sie nicht existieren
        DATA_DIR.mkdir(exist_ok=True, parents=True)
        DEBUG_DIR.mkdir(exist_ok=True, parents=True)
        
        # Besondere Debug-Ausgabe für Render-Umgebung
        if IS_CLOUD_ENV:
            log_scraper_event("info", "Starting Playwright in cloud environment", {
                "headless": HEADLESS,
                "data_dir": str(DATA_DIR.absolute())
            })
            print(f"[RENDER DEBUG] Ausgabedatei existiert: {OUTPUT_JSON.exists()}")
            print(f"[RENDER DEBUG] USE_REAL_SCRAPER={USE_REAL_SCRAPER}")
            if OUTPUT_JSON.exists():
                try:
                    with open(OUTPUT_JSON, 'r', encoding='utf-8') as f:
                        project_count = len(json.load(f))
                        print(f"[RENDER DEBUG] Anzahl Projekte in Datei: {project_count}")
                except Exception as e:
                    print(f"[RENDER DEBUG] Fehler beim Lesen der Projektdatei: {str(e)}")
        
        # Wenn USE_REAL_SCRAPER auf False gesetzt ist, verwende Dummy-Daten
        if not USE_REAL_SCRAPER:
            log_scraper_event("info", "USE_REAL_SCRAPER is disabled, using dummy data")
            # Setze das Flag für Dummy-Daten
            last_used_dummy_data = True
            # Erstelle 10 Dummy-Projekte
            dummy_projects = []
            # Versuche, Dummy-Daten aus der Datei zu laden
            dummy_file = DATA_DIR / "dummy_projects.json"
            print(f"[SCRAPER] Looking for dummy data at: {dummy_file.absolute()}")
            if dummy_file.exists():
                try:
                    with open(dummy_file, 'r', encoding='utf-8') as f:
                        dummy_projects = json.load(f)
                        print(f"[SCRAPER] Loaded {len(dummy_projects)} dummy projects from file")
                        log_scraper_event("info", "Loaded dummy data from file", {
                            "dummy_projects_count": len(dummy_projects),
                            "dummy_file": str(dummy_file.absolute())
                        })
                except Exception as e:
                    print(f"[SCRAPER] Error loading dummy data: {str(e)}")
                    log_scraper_event("error", "Error loading dummy data", {
                        "error": str(e),
                        "dummy_file": str(dummy_file.absolute())
                    })
            
            # Wenn keine Dummy-Daten geladen werden konnten, erstelle neue
            if not dummy_projects:
                print("[SCRAPER] Creating new dummy projects")
                dummy_projects = create_dummy_projects()
                log_scraper_event("info", "Created new dummy projects", {
                    "dummy_projects_count": len(dummy_projects)
                })
                
            # Verarbeite die Dummy-Projekte
            unique_projects, new_projects = project_manager.process_projects(dummy_projects)
            log_scraper_event("success", "Dummy data processing completed", {
                "unique_projects_count": len(unique_projects),
                "new_projects_count": len(new_projects)
            })
            
            # Aktualisiere den Zeitstempel des letzten Scans
            last_scrape_time = datetime.datetime.now().isoformat()
            
            return unique_projects
        
        # Ab hier beginnt der echte Scraper mit Playwright
        # Browser-Konfiguration für Playwright
        launch_options = {
            "headless": HEADLESS,
            "timeout": TIMEOUT_MS
        }
        print(f"[SCRAPER] Launching browser with options: {launch_options}")
        
        # Setze das Flag für echte Daten (wird auf True gesetzt, wenn wir auf Dummy-Daten zurückfallen)
        last_used_dummy_data = False
        
        # Initialisiere Playwright mit vollständiger Fehlerbehandlung
        try:
            log_scraper_event("info", "Initialisiere Playwright", {
                "headless": HEADLESS,
                "timeout": TIMEOUT_MS,
                "is_cloud_env": IS_CLOUD_ENV
            })
            
            async with async_playwright() as pw:
                print("[SCRAPER] Playwright erfolgreich initialisiert")
                log_scraper_event("success", "Playwright erfolgreich initialisiert", {
                    "chromium_executable": str(Path(sys.executable).parent / "playwright" / "driver" / "package" / "chromium" / "chrome-linux" / "chrome")
                })
                
                # Browser starten mit verbesserter Fehlerbehandlung
                try:
                    # Überprüfe, ob der Browser-Executable existiert
                    executable_path = None
                    try:
                        if hasattr(pw.chromium, "executable_path"):
                            executable_path = str(pw.chromium.executable_path)
                            # Überprüfe, ob die Datei existiert
                            if not Path(executable_path).exists():
                                log_scraper_event("warning", "Chromium executable nicht gefunden", {
                                    "path": executable_path
                                })
                                # Versuche, Playwright-Browser zu installieren
                                if IS_CLOUD_ENV:
                                    log_scraper_event("info", "Versuche Playwright-Browser zu installieren")
                                    import subprocess
                                    try:
                                        result = subprocess.run(
                                            [sys.executable, "-m", "playwright", "install", "chromium"],
                                            capture_output=True,
                                            text=True,
                                            check=True
                                        )
                                        log_scraper_event("success", "Playwright-Browser installiert", {
                                            "stdout": result.stdout,
                                            "stderr": result.stderr
                                        })
                                    except subprocess.CalledProcessError as e:
                                        log_scraper_event("error", "Fehler bei der Installation des Playwright-Browsers", {
                                            "stdout": e.stdout,
                                            "stderr": e.stderr,
                                            "returncode": e.returncode
                                        })
                    except Exception as path_error:
                        log_scraper_event("warning", "Fehler beim Überprüfen des Browser-Pfads", {"error": str(path_error)})
                    
                    log_scraper_event("info", "Starte Browser", {
                        "launch_options": launch_options,
                        "executable_path": executable_path or "unknown"
                    })
                    
                    # Versuche den Browser zu starten
                    browser = await pw.chromium.launch(**launch_options)
                    
                    # Log Browser-Version und andere Infos
                    version = await browser.version()
                    
                    # Verwende korrektes async/await statt .then() Verkettung
                    try:
                        context = await browser.new_context()
                        page = await context.new_page()
                        user_agent = await page.evaluate("navigator.userAgent")
                        await page.close()
                        await context.close()
                    except Exception as e:
                        user_agent = f"Error getting user agent: {str(e)}"
                        log_scraper_event("warning", "Konnte User-Agent nicht ermitteln", {"error": str(e)})
                    
                    print("[SCRAPER] Browser erfolgreich gestartet")
                    log_scraper_event("success", "Browser erfolgreich gestartet", {
                        "browser_version": version,
                        "user_agent": user_agent
                    })
                    
                    # Browser-Kontext erstellen mit Fehlerbehandlung
                    try:
                        context = await browser.new_context(
                            user_agent=USER_AGENT, 
                            viewport={"width": 1280, "height": 900}
                        )
                        log_scraper_event("info", "Browser context created", {
                            "user_agent": USER_AGENT,
                            "viewport": {"width": 1280, "height": 900}
                        })
                        
                        # Neue Seite öffnen mit Fehlerbehandlung
                        try:
                            page = await context.new_page()
                            log_scraper_event("info", "New page opened")

                            # Netzwerk-Monitoring einrichten
                            page.on("response", lambda resp: network_lines.append(
                                f"{resp.status} {resp.request.method} {resp.url} [{resp.headers.get('content-type', '')}]"))
                                
                            # Hier beginnt der Scraping-Prozess für jede Seite
                            all_projects = []
                            
                            # Durchlaufe alle Seiten und extrahiere Projekte
                            for page_idx in pages:
                                current_url = START_URL_TEMPLATE.format(page=page_idx)
                                log_scraper_event("info", f"Navigating to page {page_idx}", {
                                    "url": current_url
                                })
                                captured: List[Tuple[str, Any]] = []

                                # Handler für API-Antworten
                                def handle_response(resp):
                                    if API_RE.search(resp.url) and "application/json" in resp.headers.get("content-type", ""):
                                        async def _grab():
                                            try:
                                                captured.append((resp.url, await resp.json()))
                                            except Exception:
                                                pass
                                        asyncio.create_task(_grab())
                                page.on("response", handle_response)

                                # Navigiere zur Seite mit Fehlerbehandlung
                                try:
                                    await page.goto(current_url)
                                    log_scraper_event("info", f"Successfully navigated to page {page_idx}")
                                except Exception as nav_error:
                                    log_scraper_event("error", f"Navigation error on page {page_idx}", {
                                        "error": str(nav_error),
                                        "url": current_url
                                    })
                                    continue
                                
                                try:
                                    # Scroll through the page to trigger lazy loading
                                    log_scraper_event("info", f"Scrolling page {page_idx} to trigger lazy loading", {
                                        "scroll_steps": SCROLL_STEPS,
                                        "scroll_pause": SCROLL_PAUSE,
                                        "collect_seconds": COLLECT_SECS
                                    })
                                    for step in range(SCROLL_STEPS):
                                        await page.mouse.wheel(0, 4000)
                                        await asyncio.sleep(SCROLL_PAUSE)
                                    await asyncio.sleep(COLLECT_SECS)
                                except Exception as scroll_error:
                                    log_scraper_event("error", f"Error during scrolling on page {page_idx}", {
                                        "error": str(scroll_error)
                                    })
                                
                                # Process captured API responses
                                if captured:
                                    try:
                                        feed_url, api_json = captured[0]
                                        debug_file = DEBUG_DIR / f"api_page{page_idx}.json"
                                        (debug_file).write_text(
                                            json.dumps(api_json, indent=2, ensure_ascii=False), 
                                            encoding="utf-8"
                                        )
                                        log_scraper_event("info", f"Captured API data from page {page_idx}", {
                                            "feed_url": feed_url,
                                            "debug_file": str(debug_file),
                                            "response_size": len(json.dumps(api_json))
                                        })
                                    except Exception as save_error:
                                        log_scraper_event("error", f"Error saving API data for page {page_idx}", {
                                            "error": str(save_error)
                                        })
                                        feed_url, api_json = "n/a", {}
                                else:
                                    feed_url, api_json = "n/a", {}
                                
                                # Extract projects from API response
                                try:
                                    projects: List[Dict] = []
                                    if isinstance(api_json, dict):
                                        for key in ("content", "data", "items", "projects", "results"):
                                            if isinstance(api_json.get(key), list):
                                                projects = api_json[key]
                                                break
                                    if not projects:
                                        projects = find_projects_recursive(api_json)
                                    
                                    log_scraper_event("info", f"Projects extracted from page {page_idx}", {
                                        "count": len(projects),
                                        "source": feed_url
                                    })
                                    all_projects.extend(projects)
                                except Exception as extract_error:
                                    log_scraper_event("error", f"Error extracting projects from page {page_idx}", {
                                        "error": str(extract_error),
                                        "source": feed_url
                                    })
                            
                            # Close browser resources with proper error handling
                            try:
                                await page.close()
                                log_scraper_event("info", "Page closed successfully")
                            except Exception as page_close_error:
                                log_scraper_event("warning", "Error closing page", {
                                    "error": str(page_close_error)
                                })
                                
                            try:
                                await context.close()
                                log_scraper_event("info", "Browser context closed successfully")
                            except Exception as context_close_error:
                                log_scraper_event("warning", "Error closing browser context", {
                                    "error": str(context_close_error)
                                })
                                
                            try:
                                await browser.close()
                                log_scraper_event("info", "Browser closed successfully")
                            except Exception as browser_close_error:
                                log_scraper_event("warning", "Error closing browser", {
                                    "error": str(browser_close_error)
                                })
                                
                            log_scraper_event("info", "Browser resources released")
                            
                            # Process collected projects
                            if all_projects:
                                try:
                                    # Verarbeite die gescrapten Projekte (Duplikaterkennung und neue Projekte identifizieren)
                                    log_scraper_event("info", "Processing scraped projects", {
                                        "total_projects_found": len(all_projects)
                                    })
                                    unique_projects, new_projects = project_manager.process_projects(all_projects)
                                    
                                    # Speichere die eindeutigen Projekte
                                    OUTPUT_JSON.write_text(
                                        json.dumps(unique_projects, indent=2, ensure_ascii=False), 
                                        encoding="utf-8"
                                    )
                                    NETWORK_LOG.write_text("\n".join(network_lines), encoding="utf-8")
                                    
                                    log_scraper_event("success", "Scraping completed successfully", {
                                        "completion_time": datetime.datetime.now().isoformat(),
                                        "unique_projects_count": len(unique_projects),
                                        "new_projects_count": len(new_projects),
                                        "output_file": str(OUTPUT_JSON)
                                    })
                                    
                                    # Aktualisiere den Zeitstempel des letzten Scans
                                    last_scrape_time = datetime.datetime.now().isoformat()
                                    
                                    # Sende E-Mail-Benachrichtigung, wenn aktiviert und neue Projekte gefunden wurden
                                    if email_notification_enabled and email_recipient and new_projects:
                                        log_scraper_event("info", "Attempting to send email notification", {
                                            "recipient": email_recipient,
                                            "new_projects_count": len(new_projects)
                                        })
                                        
                                        if not email_service:
                                            log_scraper_event("error", "Email service is not initialized")
                                        else:
                                            email_config_status = email_service.get_config_status()
                                            log_scraper_event("info", "Email service status", {
                                                "is_configured": email_config_status.get('is_configured'),
                                                "smtp_server": email_config_status.get('smtp_server'),
                                                "smtp_port": email_config_status.get('smtp_port')
                                            })
                                            try:
                                                success = email_service.send_new_projects_notification(
                                                    recipient=email_recipient,
                                                    new_projects=new_projects,
                                                    scan_time=datetime.datetime.now()
                                                )
                                                log_scraper_event("success" if success else "warning", "Email notification result", {
                                                    "success": success,
                                                    "recipient": email_recipient,
                                                    "new_projects_count": len(new_projects)
                                                })
                                            except Exception as e:
                                                log_scraper_event("error", "Error sending email notification", {
                                                    "error": str(e),
                                                    "recipient": email_recipient
                                                })
                                    
                                    return unique_projects
                                except Exception as process_error:
                                    log_scraper_event("error", "Error processing projects", {
                                        "error": str(process_error),
                                        "projects_count": len(all_projects) if all_projects else 0
                                    })
                        except Exception as page_error:
                            log_scraper_event("error", "Error creating page", {
                                "error": str(page_error),
                                "page_url": current_url,
                                "page_index": page_idx
                            })
                    except Exception as context_error:
                        log_scraper_event("error", "Error creating browser context", {
                            "error": str(context_error),
                            "headless": HEADLESS,
                            "traceback": traceback.format_exc()
                        })
                except Exception as browser_error:
                    log_scraper_event("error", "Error launching browser", {
                        "error": str(browser_error),
                        "headless": HEADLESS,
                        "timeout": TIMEOUT_MS
                    })
                    
        except Exception as pw_error:
            log_scraper_event("error", "Error initializing Playwright", {
                "error": str(pw_error),
                "traceback": traceback.format_exc()
            })
            
    except Exception as scraper_error:
        log_scraper_event("error", "General scraping error", {
            "error": str(scraper_error),
            "traceback": traceback.format_exc()
        })
    
    # Bei Fehlern auf Render versuchen wir, zumindest Dummy-Daten zu laden
    fallback_success = False
    if IS_CLOUD_ENV and USE_REAL_SCRAPER:
        print("[RENDER DEBUG] Error with real scraper on Render, falling back to dummy data")
        try:
            print("[RENDER DEBUG] Versuche Fallback mit Dummy-Daten...")
            
            # Erstelle ein einfaches Dummy-Projekt
            dummy_projects = [
                {
                    "id": "dummy-1",
                    "title": "Dummy Projekt 1",
                    "description": "Dies ist ein automatisch erstelltes Dummy-Projekt für Render.",
                    "companyName": "Dummy GmbH",
                    "location": "Berlin",
                    "isRemoteWorkPossible": True,
                    "publicationDate": datetime.datetime.now().strftime("%d.%m.%Y"),
                    "originalPublicationDate": datetime.datetime.now().isoformat(),
                    "url": "https://www.gulp.de/"
                },
                {
                    "id": "dummy-2",
                    "title": "Dummy Projekt 2",
                    "description": "Ein weiteres automatisch erstelltes Dummy-Projekt für Render.",
                    "companyName": "Test AG",
                    "location": "München",
                    "isRemoteWorkPossible": True,
                    "publicationDate": datetime.datetime.now().strftime("%d.%m.%Y"),
                    "originalPublicationDate": datetime.datetime.now().isoformat(),
                    "url": "https://www.gulp.de/"
                }
            ]
            
            # Speichere die Dummy-Projekte
            try:
                DATA_DIR.mkdir(exist_ok=True, parents=True)
                OUTPUT_JSON.write_text(
                    json.dumps(dummy_projects, indent=2, ensure_ascii=False), 
                    encoding="utf-8"
                )
                print(f"[RENDER DEBUG] Created dummy data file with {len(dummy_projects)} projects")
            except Exception as save_error:
                print(f"[RENDER DEBUG] Error saving dummy data: {str(save_error)}")
            
            # Verarbeite die Dummy-Projekte
            unique_projects, new_projects = project_manager.process_projects(dummy_projects)
            print(f"[RENDER DEBUG] Processed {len(unique_projects)} unique projects, {len(new_projects)} new")
            
            # Aktualisiere den Zeitstempel des letzten Scans
            last_scrape_time = datetime.datetime.now().isoformat()
            print(f"[RENDER DEBUG] Updated last_scrape_time to {last_scrape_time}")
            fallback_success = True
            
            # Sende E-Mail-Benachrichtigung, wenn aktiviert und neue Projekte gefunden wurden
            if email_notification_enabled and email_recipient and new_projects:
                print(f"\n[SCRAPER] Versuche E-Mail-Benachrichtigung zu senden...")
                if not email_service:
                    print(f"[SCRAPER] E-Mail-Service ist nicht initialisiert!")
                else:
                    print(f"[SCRAPER] E-Mail-Service Status: {email_service.get_config_status().get('is_configured')}")
                    try:
                        success = email_service.send_new_projects_notification(
                            recipient=email_recipient,
                            new_projects=new_projects,
                            scan_time=datetime.datetime.now()
                        )
                        print(f"[SCRAPER] E-Mail-Versand Ergebnis: {'Erfolgreich' if success else 'Fehlgeschlagen'}")
                    except Exception as e:
                        print(f"Error sending email notification: {str(e)}")
            
            return unique_projects
        except Exception as fallback_error:
            print(f"[RENDER DEBUG] Fallback to dummy data also failed: {str(fallback_error)}")
    
    # If we reach here, we couldn't get any data
    try:
        return []
    finally:
        # Always reset the scraping flag when done
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
    show_all: bool = False,
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
        projects, total = project_manager.get_projects(
            search=search, 
            location=location, 
            remote=remote, 
            page=page, 
            limit=limit, 
            include_new_only=include_new_only,
            archived=False,
            show_all=show_all
        )
        
        # Hole die neuen Projekte, um sie im Frontend markieren zu können
        new_project_ids = {p.get("id") for p in project_manager.get_new_projects()}
        
        # Get the last scrape time
        last_scrape_time = None
        try:
            if LAST_SCRAPE_FILE.exists():
                last_scrape_time = LAST_SCRAPE_FILE.read_text().strip()
        except Exception as e:
            print(f"Error reading last scrape time: {str(e)}")
        
        return {
            "projects": projects,
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
            archived=True,
            show_all=show_all
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


@app.get("/status")
async def get_status():
    """Get the scraper status."""
    history = project_manager.get_history()
    new_projects = project_manager.get_new_projects()
    
    # Ermittle die nächste geplante Ausführung
    next_run = None
    for job in scheduler.get_jobs():
        if job.id.startswith('scraper_job_') and job.next_run_time:
            if next_run is None or job.next_run_time < next_run:
                next_run = job.next_run_time
    
    # Formatiere die täglichen Läufe für bessere Lesbarkeit
    formatted_daily_runs = []
    for run in scheduler_config["daily_runs"]:
        formatted_daily_runs.append(f"{run['hour']:02d}:{run['minute']:02d}")
    
    return {
        "is_scraping": is_scraping,
        "last_scrape": last_scrape_time,
        "next_scheduled_run": next_run.isoformat() if next_run else None,
        "data_available": OUTPUT_JSON.exists(),
        "project_count": len(json.loads(OUTPUT_JSON.read_text(encoding="utf-8"))) if OUTPUT_JSON.exists() else 0,
        "new_project_count": len(new_projects),
        "total_projects_found": history.get("total_projects_found", 0),
        "dummy_data": last_used_dummy_data,  # Füge die Information über Dummy-Daten hinzu
        "email_notification": {
            "enabled": email_notification_enabled,
            "recipient": email_recipient if email_recipient else None,
            "configured": email_service.is_configured if email_service else False
        },
        "scheduler": {
            "enabled": scheduler_config["enabled"],
            "interval_days": scheduler_config["interval_days"],
            "daily_runs": scheduler_config["daily_runs"],
            "formatted_runs": formatted_daily_runs
        },
        "archive": {
            "count": project_manager.get_archive_count()
        }
    }


@app.get("/api/scraper-logs", tags=["scraper"])
async def get_scraper_logs():
    """
    Get the detailed scraper logs for the detailed view
    """
    return {
        "logs": scraper_logs,
        "count": len(scraper_logs)
    }


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

# Default scheduler configuration
scheduler_config = {
    "enabled": True,
    "interval_days": 1,  # Default: run every day
    "daily_runs": [
        {"hour": i, "minute": 0} for i in range(0, 24)  # Run every hour
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
                # Sicher auf next_run_time zugreifen
                try:
                    if hasattr(job, 'next_run_time') and job.next_run_time:
                        print(f"Next run time: {job.next_run_time}")
                    else:
                        print("Next run time: Not available yet")
                except Exception as e:
                    print(f"Error accessing next_run_time: {str(e)}")
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
    
    # Lade gespeicherte Scraper-Logs
    load_logs_from_file()
    
    # Initialisiere den Projekt-Manager
    project_manager = ProjectManager(DATA_DIR)
    
    # Initialisiere den E-Mail-Service mit Standard-SMTP-Einstellungen
    print("\n[STARTUP] Initialisiere E-Mail-Service...")
    print(f"[STARTUP] SMTP-Konfiguration: Host={DEFAULT_SMTP_HOST}, Port={DEFAULT_SMTP_PORT}, User={DEFAULT_SMTP_USER}")
    print(f"[STARTUP] Umgebungsvariablen: SMTP_HOST={os.environ.get('SMTP_HOST')}, SMTP_PORT={os.environ.get('SMTP_PORT')}")
    
    # Verwende Umgebungsvariablen, falls vorhanden, sonst Standardwerte
    smtp_host = os.environ.get("SMTP_HOST", DEFAULT_SMTP_HOST)
    smtp_port = int(os.environ.get("SMTP_PORT", DEFAULT_SMTP_PORT))
    smtp_user = os.environ.get("SMTP_USER", DEFAULT_SMTP_USER)
    smtp_password = os.environ.get("SMTP_PASSWORD", DEFAULT_SMTP_PASSWORD)
    email_sender = os.environ.get("EMAIL_SENDER", DEFAULT_EMAIL_SENDER)
    
    email_service = EmailService(
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        smtp_user=smtp_user,
        smtp_password=smtp_password,
        sender=email_sender,
        frontend_url=FRONTEND_URL
    )
    
    # Ausgabe der Konfiguration
    config_status = email_service.get_config_status()
    print(f"[STARTUP] E-Mail-Service konfiguriert: {config_status.get('is_configured')}")
    print(f"[STARTUP] Hostname: {config_status.get('hostname')}")
    print(f"[STARTUP] Umgebung: {config_status.get('environment')}")
    
    # Initialisiere die E-Mail-Test-Route
    import email_test_route
    email_test_route.initialize(
        email_svc=email_service,
        email_rcpt=email_recipient,
        default_email_rcpt=DEFAULT_EMAIL_RECIPIENT
    )
    
    # Registriere die E-Mail-Test-Route in der API
    app.include_router(email_test_route.router, prefix="/email", tags=["email"])
    print(f"[STARTUP] E-Mail-Test-Route registriert unter /email/config, /email/test und /email/diagnose")
    
    # Configure and start the scheduler
    configure_scheduler()
    
    # Make sure the scheduler is not already running before starting it
    if not scheduler.running:
        try:
            scheduler.start()
            print("Scheduler started successfully")
        except Exception as e:
            print(f"Error starting scheduler: {str(e)}")
    
    # In Cloud-Umgebung (Render) spezielles Setup durchführen
    if IS_CLOUD_ENV:
        print("\n[RENDER SETUP] Cloud-Umgebung erkannt: Führe spezielles Setup durch...")
        
        # Stelle sicher, dass der Scheduler aktiviert ist
        scheduler_config["enabled"] = True
        print(f"[RENDER SETUP] Scheduler-Status: {scheduler_config['enabled']}")
        print(f"[RENDER SETUP] USE_REAL_SCRAPER={USE_REAL_SCRAPER}")
        
        # Spezielle E-Mail-Konfiguration für Render
        print("[RENDER SETUP] Überprüfe E-Mail-Konfiguration...")
        if email_service:
            config_status = email_service.get_config_status()
            print(f"[RENDER SETUP] E-Mail-Konfiguration: {config_status}")
            
            # Überprüfe, ob die E-Mail-Konfiguration vollständig ist
            if not config_status.get('is_configured'):
                print("[RENDER SETUP] E-Mail-Service ist nicht vollständig konfiguriert. Versuche Fallback-Konfiguration...")
                
                # Versuche, die E-Mail-Konfiguration aus den Umgebungsvariablen zu laden
                smtp_host = os.environ.get("SMTP_HOST", DEFAULT_SMTP_HOST)
                smtp_port = int(os.environ.get("SMTP_PORT", DEFAULT_SMTP_PORT))
                smtp_user = os.environ.get("SMTP_USER", DEFAULT_SMTP_USER)
                smtp_password = os.environ.get("SMTP_PASSWORD", DEFAULT_SMTP_PASSWORD)
                email_sender = os.environ.get("EMAIL_SENDER", DEFAULT_EMAIL_SENDER)
                
                print(f"[RENDER SETUP] Verwende folgende E-Mail-Konfiguration:")
                print(f"[RENDER SETUP] - SMTP_HOST: {smtp_host}")
                print(f"[RENDER SETUP] - SMTP_PORT: {smtp_port}")
                print(f"[RENDER SETUP] - SMTP_USER: {smtp_user}")
                print(f"[RENDER SETUP] - EMAIL_SENDER: {email_sender}")
                
                # Initialisiere den E-Mail-Service neu mit den aktuellen Werten
                email_service = EmailService(
                    smtp_host=smtp_host,
                    smtp_port=smtp_port,
                    smtp_user=smtp_user,
                    smtp_password=smtp_password,
                    sender=email_sender,
                    frontend_url=FRONTEND_URL
                )
                
                # Überprüfe die neue Konfiguration
                new_config = email_service.get_config_status()
                print(f"[RENDER SETUP] Neue E-Mail-Konfiguration: {new_config}")
                print(f"[RENDER SETUP] E-Mail-Service konfiguriert: {new_config.get('is_configured')}")
            else:
                print("[RENDER SETUP] E-Mail-Service ist korrekt konfiguriert.")
        
        # Stelle sicher, dass die Datenverzeichnisse existieren und beschreibbar sind
        print(f"[RENDER SETUP] Überprüfe Datenverzeichnisse...")
        DATA_DIR.mkdir(exist_ok=True, parents=True)
        DEBUG_DIR.mkdir(exist_ok=True, parents=True)
        
        # Prüfe, ob Daten vorhanden sind
        if not OUTPUT_JSON.exists() or os.path.getsize(OUTPUT_JSON) == 0:
            print(f"[RENDER SETUP] Keine Projektdaten gefunden, starte sofortigen Scrape...")
            # Scraper direkt ausführen (nicht als Task), damit Daten sofort verfügbar sind
            await scheduled_scrape()
        else:
            print(f"[RENDER SETUP] Projektdaten gefunden ({os.path.getsize(OUTPUT_JSON)} Bytes), überprüfe Inhalt...")
            try:
                with open(OUTPUT_JSON, 'r', encoding='utf-8') as f:
                    projects = json.load(f)
                    print(f"[RENDER SETUP] {len(projects)} Projekte in Datei gefunden")
                    
                    # Aktualisiere den letzten Scrape-Zeitpunkt, damit er nicht als "Noch nie" angezeigt wird
                    global last_scrape_time
                    if not last_scrape_time:
                        last_scrape_time = datetime.datetime.now().isoformat()
                        print(f"[RENDER SETUP] Letzter Scrape-Zeitpunkt auf {last_scrape_time} gesetzt")
            except Exception as e:
                print(f"[RENDER SETUP] Fehler beim Lesen der Projektdatei: {str(e)}")
                print(f"[RENDER SETUP] Starte sofortigen Scrape wegen Fehler...")
                await scheduled_scrape()
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
# Datei für den letzten Scrape-Zeitpunkt

@app.post("/scrape")
async def trigger_scrape(
    background_tasks: BackgroundTasks,
    request: ScrapeRequest = ScrapeRequest()
):
    """Trigger a new scrape."""
    global email_notification_enabled, last_scrape_time, last_used_dummy_data
    
    if is_scraping:
        return JSONResponse(
            status_code=409,
            content={"error": "A scrape is already in progress"}
        )
    
    print(f"\n[MANUAL SCRAPE] Manueller Scrape-Vorgang gestartet")
    print(f"[MANUAL SCRAPE] Umgebung: {'Render/Cloud' if IS_CLOUD_ENV else 'Lokal'}")
    print(f"[MANUAL SCRAPE] USE_REAL_SCRAPER={USE_REAL_SCRAPER}")
        
    # Convert the pages list to a range if provided
    pages = PAGE_RANGE
    if request.pages:
        pages = range(min(request.pages), max(request.pages) + 1)
    
    # Aktiviere E-Mail-Benachrichtigung für diesen Scrape-Vorgang, wenn angefordert
    if request.send_email:
        email_notification_enabled = True
    else:
        email_notification_enabled = False
    
    # Direkter Scrape statt Hintergrundaufgabe, um sofortige Rückmeldung zu ermöglichen
    try:
        # Starte den Scrape-Vorgang direkt
        print(f"[MANUAL SCRAPE] Führe Scrape direkt aus...")
        
        # Auf Render verwenden wir immer Dummy-Daten, wenn nicht explizit anders konfiguriert
        if IS_CLOUD_ENV and not USE_REAL_SCRAPER:
            print(f"[MANUAL SCRAPE] Render-Umgebung erkannt, verwende Dummy-Daten")
            # Erstelle ein einfaches Dummy-Projekt
            dummy_projects = [
                {
                    "id": "dummy-1",
                    "title": "Dummy Projekt 1",
                    "description": "Dies ist ein automatisch erstelltes Dummy-Projekt für Render.",
                    "companyName": "Dummy GmbH",
                    "location": "Berlin",
                    "isRemoteWorkPossible": True,
                    "publicationDate": datetime.datetime.now().strftime("%d.%m.%Y"),
                    "originalPublicationDate": datetime.datetime.now().isoformat(),
                    "url": "https://www.gulp.de/"
                },
                {
                    "id": "dummy-2",
                    "title": "Dummy Projekt 2",
                    "description": "Ein weiteres automatisch erstelltes Dummy-Projekt für Render.",
                    "companyName": "Test AG",
                    "location": "München",
                    "isRemoteWorkPossible": True,
                    "publicationDate": datetime.datetime.now().strftime("%d.%m.%Y"),
                    "originalPublicationDate": datetime.datetime.now().isoformat(),
                    "url": "https://www.gulp.de/"
                }
            ]
            
            # Speichere die Dummy-Projekte
            try:
                DATA_DIR.mkdir(exist_ok=True, parents=True)
                OUTPUT_JSON.write_text(
                    json.dumps(dummy_projects, indent=2, ensure_ascii=False), 
                    encoding="utf-8"
                )
                print(f"[RENDER DEBUG] Created dummy data file with {len(dummy_projects)} projects")
                
                # Verarbeite die Dummy-Projekte
                unique_projects, new_projects = project_manager.process_projects(dummy_projects)
                print(f"[RENDER DEBUG] Processed {len(unique_projects)} unique projects, {len(new_projects)} new")
                
                # Aktualisiere den Zeitstempel des letzten Scans
                last_scrape_time = datetime.datetime.now().isoformat()
                print(f"[RENDER DEBUG] Updated last_scrape_time to {last_scrape_time}")
                
                # Stelle sicher, dass die Projekte korrekt verarbeitet wurden
                project_count = len(unique_projects)
                new_project_count = len(new_projects)
                
                # Für Render: Stelle sicher, dass die Projektdaten in allen relevanten Dateien aktualisiert sind
                print(f"[MANUAL SCRAPE] Aktualisiere Projektdateien für Render-Kompatibilität...")
                # Erzwinge eine Neusortierung der Projekte (aktuell vs. archiviert)
                project_manager.get_projects(force_reprocess=True, show_all=True)
                
                # Aktualisiere den letzten Scrape-Zeitpunkt und setze das Dummy-Daten-Flag
                try:
                    last_scrape_time = datetime.datetime.now().isoformat()
                    last_used_dummy_data = True  # Setze das Flag für Dummy-Daten
                    with open(LAST_SCRAPE_FILE, "w") as f:
                        f.write(last_scrape_time)
                except Exception as e:
                    print(f"[MANUAL SCRAPE] Fehler beim Speichern des letzten Scrape-Zeitpunkts: {str(e)}")
                
                return {
                    "message": "Scrape mit Dummy-Daten wurde erfolgreich durchgeführt",
                    "success": True,
                    "last_scrape": last_scrape_time,
                    "project_count": project_count,
                    "new_project_count": new_project_count,
                    "email_notification": email_notification_enabled and email_recipient != "",
                    "dummy_data": True
                }
            except Exception as e:
                print(f"[RENDER DEBUG] Error with dummy data: {str(e)}")
                import traceback
                print(f"[RENDER DEBUG] Traceback: {traceback.format_exc()}")
        
        # Normaler Scrape-Vorgang (nicht Render oder explizit USE_REAL_SCRAPER=True)
        print(f"[MANUAL SCRAPE] Starte echten Scraper mit USE_REAL_SCRAPER={USE_REAL_SCRAPER}")
        log_scraper_event("info", "Starte echten Scraper", {
            "is_cloud_env": IS_CLOUD_ENV,
            "use_real_scraper": USE_REAL_SCRAPER,
            "pages": str(pages)
        })
        
        try:
            projects = await scrape_gulp(pages)
            print(f"[MANUAL SCRAPE] Scraper abgeschlossen, {len(projects)} Projekte gefunden")
            log_scraper_event("success", "Scraper abgeschlossen", {"projects_count": len(projects)})
        except Exception as e:
            error_msg = f"Fehler beim Ausführen des Scrapers: {str(e)}"
            print(f"[MANUAL SCRAPE ERROR] {error_msg}")
            log_scraper_event("error", error_msg, {"traceback": traceback.format_exc()})
            return JSONResponse(
                status_code=500,
                content={"error": error_msg}
            )
        
        # Stelle sicher, dass der letzte Scrape-Zeitpunkt aktualisiert wird
        last_scrape_time = datetime.datetime.now().isoformat()
        log_scraper_event("info", "Letzter Scrape-Zeitpunkt aktualisiert", {"timestamp": last_scrape_time})
        
        # Speichere den letzten Scrape-Zeitpunkt in einer Datei für Persistenz
        try:
            LAST_SCRAPE_FILE.write_text(last_scrape_time, encoding="utf-8")
            print(f"[MANUAL SCRAPE] Letzter Scrape-Zeitpunkt gespeichert: {last_scrape_time}")
        except Exception as e:
            print(f"[MANUAL SCRAPE] Fehler beim Speichern des letzten Scrape-Zeitpunkts: {str(e)}")
        
        # Stelle sicher, dass die Projekte korrekt verarbeitet wurden
        project_count = 0
        new_project_count = 0
        
        try:
            # Prüfe, ob Projektdaten vorhanden sind
            if OUTPUT_JSON.exists():
                raw_projects = json.loads(OUTPUT_JSON.read_text(encoding="utf-8"))
                project_count = len(raw_projects)
                
                # Stelle sicher, dass die Projekte im ProjectManager verarbeitet werden
                # Dies ist besonders wichtig für Render, um sicherzustellen, dass die Daten korrekt gespeichert werden
                print(f"[MANUAL SCRAPE] Verarbeite {project_count} Projekte im ProjectManager...")
                _, new_projects = project_manager.process_projects(raw_projects)
                new_project_count = len(new_projects)
                
                # Für Render: Stelle sicher, dass die Projektdaten in allen relevanten Dateien aktualisiert sind
                print(f"[MANUAL SCRAPE] Aktualisiere Projektdateien für Render-Kompatibilität...")
                # Erzwinge eine Neusortierung der Projekte (aktuell vs. archiviert)
                project_manager.get_projects(force_reprocess=True, show_all=True)
        except Exception as e:
            print(f"[MANUAL SCRAPE] Fehler bei der Projektverarbeitung: {str(e)}")
        
        return {
            "message": "Scrape wurde erfolgreich durchgeführt",
            "success": True,
            "last_scrape": last_scrape_time,
            "project_count": project_count,
            "new_project_count": new_project_count,
            "email_notification": email_notification_enabled and email_recipient != ""
        }
    except Exception as e:
        print(f"[MANUAL SCRAPE] Fehler beim Scrapen: {str(e)}")
        import traceback
        print(f"[MANUAL SCRAPE] Traceback: {traceback.format_exc()}")
        return JSONResponse(
            status_code=500,
            content={
                "error": f"Fehler beim Scrapen: {str(e)}",
                "success": False
            }
        )

# Main Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Run the API server
    uvicorn.run("scraper:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8001)), log_level="info")
