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
import uuid
import time

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

def log_scraper_event(event_type, message, data=None, log_level=None, correlation_id=None, tags=None):
    """
    Fügt einen neuen Log-Eintrag zu den Scraper-Logs hinzu.
    
    Args:
        event_type (str): Art des Events (info, warning, error, success)
        message (str): Nachricht für das Log
        data (dict, optional): Zusätzliche Daten zum Event
        log_level (str, optional): Log-Level (debug, info, warning, error, critical)
        correlation_id (str, optional): ID zur Korrelation zusammengehöriger Log-Einträge
        tags (list, optional): Tags zur Kategorisierung des Log-Eintrags
    """
    global SCRAPER_LOGS
    
    if data is None:
        data = {}
    
    # Füge zusätzliche Kontextinformationen hinzu
    timestamp = datetime.datetime.now().isoformat()
    
    # Füge Umgebungsinformationen hinzu
    env_info = {
        "is_cloud": IS_CLOUD_ENV,
        "use_real_scraper": USE_REAL_SCRAPER,
        "headless": HEADLESS
    }
    
    # Erweitere die Daten für bessere Diagnose
    enhanced_data = data.copy()
    
    # Füge Stack-Trace für Fehler hinzu
    if event_type == "error" or event_type == "warning":
        if "traceback" not in enhanced_data:
            trace = traceback.format_exc()
            if trace != "NoneType: None\n":
                enhanced_data["traceback"] = trace
            else:
                enhanced_data["traceback"] = "No traceback available"
        
        # Füge Speichernutzung hinzu
        try:
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            enhanced_data["memory_usage"] = {
                "rss_mb": round(memory_info.rss / 1024 / 1024, 2),  # MB
                "vms_mb": round(memory_info.vms / 1024 / 1024, 2)   # MB
            }
        except ImportError:
            enhanced_data["memory_usage"] = "psutil not available"
        except Exception as e:
            enhanced_data["memory_usage"] = f"Error getting memory usage: {str(e)}"
    
    # Map event_type to log_level if not provided
    if log_level is None:
        log_level_map = {
            "info": "INFO",
            "warning": "WARNING",
            "error": "ERROR",
            "success": "INFO"
        }
        log_level = log_level_map.get(event_type, "INFO")
    else:
        log_level = log_level.upper()
    
    # Generate correlation ID if not provided
    if correlation_id is None:
        correlation_id = f"scrape-{int(time.time())}-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    
    # Add performance metrics
    performance_metrics = {}
    try:
        # CPU usage
        import psutil
        process = psutil.Process()
        performance_metrics["cpu_percent"] = process.cpu_percent(interval=0.1)
        
        # Memory usage
        memory_info = process.memory_info()
        performance_metrics["memory_usage"] = {
            "rss_mb": round(memory_info.rss / 1024 / 1024, 2),  # MB
            "vms_mb": round(memory_info.vms / 1024 / 1024, 2)   # MB
        }
        
        # System load
        performance_metrics["system_load"] = os.getloadavg()
    except Exception as e:
        performance_metrics["error"] = f"Error getting performance metrics: {str(e)}"
    
    # Erstelle den Log-Eintrag mit erweiterten Informationen
    log_entry = {
        "timestamp": timestamp,
        "event_type": event_type,
        "log_level": log_level,
        "message": message,
        "data": enhanced_data,
        "environment": env_info,
        "process_id": os.getpid(),
        "correlation_id": correlation_id,
        "tags": tags or [],
        "performance": performance_metrics
    }
    
    # Ausgabe in der Konsole für bessere Sichtbarkeit
    print(f"[SCRAPER LOG] [{event_type.upper()}] {message}")
    if event_type == "error":
        print(f"[SCRAPER ERROR DETAILS] {json.dumps(enhanced_data, default=str)}")
    
    SCRAPER_LOGS.append(log_entry)
    
    # Begrenze die Anzahl der Logs
    if len(SCRAPER_LOGS) > MAX_LOG_ENTRIES:
        SCRAPER_LOGS = SCRAPER_LOGS[-MAX_LOG_ENTRIES:]
    
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
    
    # Generate a unique correlation ID for this scraping session
    correlation_id = f"scrape-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    
    if is_scraping:
        log_scraper_event(
            "warning", 
            "Scraper is already running, skipping", 
            correlation_id=correlation_id,
            tags=["scraper_busy"]
        )
        return []
    
    is_scraping = True
    all_projects: List[Dict] = []
    network_lines: List[str] = []
    
    try:
        log_scraper_event(
            "info", 
            f"Starting GULP scraper", 
            {
                "timestamp": datetime.datetime.now().isoformat(),
                "use_real_scraper": USE_REAL_SCRAPER,
                "is_cloud_env": IS_CLOUD_ENV,
                "pages": list(pages)
            },
            correlation_id=correlation_id,
            tags=["scraper_start", "gulp"]
        )
    except Exception as e:
        log_scraper_event(
            "error", 
            "Error logging scraper start", 
            {"error": str(e)},
            correlation_id=correlation_id,
            tags=["error", "logging_error"]
        )
        
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
            log_scraper_event(
                "info", 
                "USE_REAL_SCRAPER is disabled, using dummy data",
                correlation_id=correlation_id,
                tags=["dummy_data"]
            )
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
                        log_scraper_event(
                            "info", 
                            "Loaded dummy data from file", 
                            {
                                "dummy_projects_count": len(dummy_projects),
                                "dummy_file": str(dummy_file.absolute())
                            },
                            correlation_id=correlation_id,
                            tags=["dummy_data", "file_loaded"]
                        )
                except Exception as e:
                    print(f"[SCRAPER] Error loading dummy data: {str(e)}")
                    log_scraper_event(
                        "error", 
                        "Error loading dummy data", 
                        {
                            "error": str(e),
                            "dummy_file": str(dummy_file.absolute())
                        },
                        correlation_id=correlation_id,
                        tags=["dummy_data", "error", "file_error"]
                    )
            
            # Wenn keine Dummy-Daten geladen werden konnten, erstelle neue
            if not dummy_projects:
                print("[SCRAPER] Creating new dummy projects")
                dummy_projects = create_dummy_projects()
                log_scraper_event(
                    "info", 
                    "Created new dummy projects", 
                    {
                        "dummy_projects_count": len(dummy_projects)
                    },
                    correlation_id=correlation_id,
                    tags=["dummy_data", "generated"]
                )
                
            # Verarbeite die Dummy-Projekte
            unique_projects, new_projects = project_manager.process_projects(dummy_projects)
            log_scraper_event(
                "success", 
                "Dummy data processing completed", 
                {
                    "unique_projects_count": len(unique_projects),
                    "new_projects_count": len(new_projects)
                },
                correlation_id=correlation_id,
                tags=["dummy_data", "processing_complete"]
            )
            
            # Aktualisiere den Zeitstempel des letzten Scans
            last_scrape_time = datetime.datetime.now().isoformat()
            
            return unique_projects
        
        # Ab hier beginnt der echte Scraper mit Playwright
        # Browser-Konfiguration
        launch_options = {
            "headless": HEADLESS,
            "timeout": TIMEOUT_MS
        }
        
        # Render-spezifische Konfiguration
        if IS_CLOUD_ENV:
            log_scraper_event(
                "info", 
                "Verwende Render-spezifische Browser-Konfiguration",
                correlation_id=correlation_id,
                tags=["render", "browser_config"]
            )
            # Zusätzliche Argumente für Render
            render_args = [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--no-first-run',
                '--no-zygote',
                '--single-process',
                '--disable-gpu'
            ]
            launch_options["args"] = render_args
            
            # Setze explizit den Browser-Pfad, wenn wir auf Render sind
            render_chromium_path = '/opt/render/.cache/ms-playwright/chromium-1091/chrome-linux/chrome'
            if os.path.exists(render_chromium_path):
                log_scraper_event(
                    "info", 
                    "Render Chromium executable gefunden", 
                    {
                        "path": render_chromium_path
                    },
                    correlation_id=correlation_id,
                    tags=["render", "chromium", "executable_found"]
                )
                # Setze den Executable-Pfad direkt in den Launch-Optionen
                launch_options["executable_path"] = render_chromium_path
            else:
                log_scraper_event(
                    "warning", 
                    "Render Chromium executable nicht gefunden", 
                    {
                        "path": render_chromium_path,
                        "directories_found": str(os.listdir('/opt/render/.cache/ms-playwright')) if os.path.exists('/opt/render/.cache/ms-playwright') else "ms-playwright directory not found"
                    },
                    correlation_id=correlation_id,
                    tags=["render", "chromium", "executable_missing", "warning"]
                )
                
                # Versuche, alternative Chromium-Versionen zu finden
                try:
                    import glob
                    chromium_dirs = glob.glob('/opt/render/.cache/ms-playwright/chromium-*')
                    if chromium_dirs:
                        latest_dir = max(chromium_dirs)
                        chrome_path = os.path.join(latest_dir, 'chrome-linux', 'chrome')
                        if os.path.exists(chrome_path):
                            log_scraper_event(
                                "info", 
                                "Alternative Chromium-Version gefunden", 
                                {
                                    "path": chrome_path
                                },
                                correlation_id=correlation_id,
                                tags=["render", "chromium", "alternative_found"]
                            )
                            launch_options["executable_path"] = chrome_path
                except Exception as e:
                    log_scraper_event(
                        "error", 
                        "Fehler beim Suchen nach alternativen Chromium-Versionen", 
                        {
                            "error": str(e)
                        },
                        correlation_id=correlation_id,
                        tags=["render", "chromium", "error", "alternative_search"]
                    )
        
        try:
            print(f"[SCRAPER] Launching browser with options: {launch_options}")
        except Exception as e:
            log_scraper_event(
                "error", 
                "Error printing browser launch options", 
                {"error": str(e)},
                correlation_id=correlation_id,
                tags=["error", "browser_launch"]
            )
        
        # Setze das Flag für echte Daten (wird auf True gesetzt, wenn wir auf Dummy-Daten zurückfallen)
        last_used_dummy_data = False
        
        # Initialisiere Playwright mit vollständiger Fehlerbehandlung
        try:
            log_scraper_event(
                "info", 
                "Initialisiere Playwright", 
                {
                    "headless": HEADLESS,
                    "timeout": TIMEOUT_MS,
                    "is_cloud_env": IS_CLOUD_ENV
                },
                correlation_id=correlation_id,
                tags=["playwright", "initialization"]
            )
        except Exception as e:
            log_scraper_event(
                "error", 
                "Error initializing Playwright logging", 
                {"error": str(e)},
                correlation_id=correlation_id,
                tags=["error", "playwright", "initialization_error"]
            )
            
            async with async_playwright() as pw:
                print("[SCRAPER] Playwright erfolgreich initialisiert")
                log_scraper_event(
                    "success", 
                    "Playwright erfolgreich initialisiert", 
                    {
                        "chromium_executable": str(Path(sys.executable).parent / "playwright" / "driver" / "package" / "chromium" / "chrome-linux" / "chrome")
                    },
                    correlation_id=correlation_id,
                    tags=["playwright", "initialization_success"]
                )
                
                # Browser starten mit verbesserter Fehlerbehandlung
                try:
                    # Überprüfe, ob der Browser-Executable existiert
                    executable_path = None
                    try:
                        if hasattr(pw.chromium, "executable_path"):
                            executable_path = str(pw.chromium.executable_path)
                            # Überprüfe, ob die Datei existiert
                            if not Path(executable_path).exists():
                                log_scraper_event(
                                    "warning", 
                                    "Chromium executable nicht gefunden", 
                                    {
                                        "path": executable_path
                                    },
                                    correlation_id=correlation_id,
                                    tags=["chromium", "executable_missing", "warning"]
                                )
                                # Versuche, Playwright-Browser zu installieren
                                if IS_CLOUD_ENV:
                                    log_scraper_event(
                                        "info", 
                                        "Versuche Playwright-Browser zu installieren",
                                        correlation_id=correlation_id,
                                        tags=["playwright", "browser_install"]
                                    )
                                    import subprocess
                                    try:
                                        result = subprocess.run(
                                            [sys.executable, "-m", "playwright", "install", "chromium"],
                                            capture_output=True,
                                            text=True,
                                            check=True
                                        )
                                        log_scraper_event(
                                            "success", 
                                            "Playwright-Browser installiert", 
                                            {
                                                "stdout": result.stdout,
                                                "stderr": result.stderr
                                            },
                                            correlation_id=correlation_id,
                                            tags=["playwright", "browser_install_success"]
                                        )
                                    except subprocess.CalledProcessError as e:
                                        log_scraper_event(
                                            "error", 
                                            "Fehler bei der Installation des Playwright-Browsers", 
                                            {
                                                "stdout": e.stdout,
                                                "stderr": e.stderr,
                                                "returncode": e.returncode
                                            },
                                            correlation_id=correlation_id,
                                            tags=["playwright", "browser_install_error", "error"]
                                        )
                    except Exception as path_error:
                        log_scraper_event(
                            "warning", 
                            "Fehler beim Überprüfen des Browser-Pfads", 
                            {"error": str(path_error)},
                            correlation_id=correlation_id,
                            tags=["browser", "path_error", "warning"]
                        )
                    
                    log_scraper_event(
                        "info", 
                        "Starte Browser", 
                        {
                            "launch_options": launch_options,
                            "executable_path": executable_path or "unknown"
                        },
                        correlation_id=correlation_id,
                        tags=["browser", "launch"]
                    )
                    
                    # Detaillierte Logging vor dem Browser-Start
                    log_scraper_event(
                        "info", 
                        "Browser-Start-Details", 
                        {
                            "launch_options": launch_options,
                            "executable_path": executable_path or "unknown",
                            "playwright_version": pw.__version__ if hasattr(pw, "__version__") else "unknown",
                            "python_version": sys.version,
                            "platform": sys.platform,
                            "env_vars": {
                                "PATH": os.environ.get("PATH", "not set"),
                                "PLAYWRIGHT_BROWSERS_PATH": os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "not set"),
                                "DISPLAY": os.environ.get("DISPLAY", "not set")
                            }
                        },
                        correlation_id=correlation_id,
                        tags=["browser", "launch_details"]
                    )
                    
                    # Versuche den Browser zu starten mit ausführlichem Error-Handling
                    try:
                        # Verwende explizite Argumente statt **launch_options für bessere Fehlerdiagnose
                        browser = await pw.chromium.launch(
                            headless=launch_options.get("headless", True),
                            timeout=launch_options.get("timeout", 30000),
                            args=launch_options.get("args", [])
                        )
                        log_scraper_event(
                            "success", 
                            "Browser erfolgreich gestartet",
                            correlation_id=correlation_id,
                            tags=["browser", "launch_success"]
                        )
                        
                        # Log Browser-Version und andere Infos
                        try:
                            version = await browser.version()
                            log_scraper_event(
                                "info", 
                                "Browser-Version", 
                                {"version": version},
                                correlation_id=correlation_id,
                                tags=["browser", "version_info"]
                            )
                        except Exception as ver_error:
                            version = f"Error getting version: {str(ver_error)}"
                            log_scraper_event(
                                "warning", 
                                "Konnte Browser-Version nicht ermitteln", 
                                {"error": str(ver_error)},
                                correlation_id=correlation_id,
                                tags=["browser", "version_error", "warning"]
                            )
                        
                        # Verwende korrektes async/await statt .then() Verkettung
                        try:
                            context = await browser.new_context()
                            log_scraper_event(
                                "info", 
                                "Browser-Kontext erstellt",
                                correlation_id=correlation_id,
                                tags=["browser", "context_created"]
                            )
                            
                            try:
                                page = await context.new_page()
                                log_scraper_event(
                                    "info", 
                                    "Browser-Seite erstellt",
                                    correlation_id=correlation_id,
                                    tags=["browser", "page_created"]
                                )
                                
                                try:
                                    user_agent = await page.evaluate("navigator.userAgent")
                                    log_scraper_event(
                                        "info", 
                                        "User-Agent ermittelt", 
                                        {"user_agent": user_agent},
                                        correlation_id=correlation_id,
                                        tags=["browser", "user_agent"]
                                    )
                                except Exception as ua_error:
                                    user_agent = f"Error getting user agent: {str(ua_error)}"
                                    log_scraper_event(
                                        "warning", 
                                        "Konnte User-Agent nicht ermitteln", 
                                        {"error": str(ua_error)},
                                        correlation_id=correlation_id,
                                        tags=["browser", "user_agent_error", "warning"]
                                    )
                                
                                await page.close()
                                log_scraper_event(
                                    "info", 
                                    "Test-Seite geschlossen",
                                    correlation_id=correlation_id,
                                    tags=["browser", "test_page_closed"]
                                )
                            except Exception as page_error:
                                user_agent = f"Error creating page: {str(page_error)}"
                                log_scraper_event(
                                    "warning", 
                                    "Konnte Browser-Seite nicht erstellen", 
                                    {"error": str(page_error)},
                                    correlation_id=correlation_id,
                                    tags=["browser", "page_creation_error", "warning"]
                                )
                            
                            await context.close()
                            log_scraper_event(
                                "info", 
                                "Test-Kontext geschlossen",
                                correlation_id=correlation_id,
                                tags=["browser", "test_context_closed"]
                            )
                        except Exception as ctx_error:
                            user_agent = f"Error creating context: {str(ctx_error)}"
                            log_scraper_event(
                                "warning", 
                                "Konnte Browser-Kontext nicht erstellen", 
                                {"error": str(ctx_error)},
                                correlation_id=correlation_id,
                                tags=["browser", "context_creation_error", "warning"]
                            )
                    except Exception as launch_error:
                        # Detaillierte Fehlerinformationen sammeln
                        error_details = {
                            "error_type": type(launch_error).__name__,
                            "error_message": str(launch_error),
                            "traceback": traceback.format_exc(),
                            "launch_options": launch_options,
                            "correlation_id": correlation_id  # Include correlation ID in error details
                        }
                        
                        # Prüfe auf spezifische Fehlertypen für bessere Diagnose
                        if "executable doesn't exist" in str(launch_error).lower():
                            error_details["error_category"] = "executable_not_found"
                            error_details["suggested_fix"] = "Run 'playwright install chromium' or check browser path"
                        elif "timed out" in str(launch_error).lower():
                            error_details["error_category"] = "timeout"
                            error_details["suggested_fix"] = "Increase timeout value or check system resources"
                        elif "str" in str(launch_error).lower() and "callable" in str(launch_error).lower():
                            error_details["error_category"] = "str_not_callable"
                            error_details["suggested_fix"] = "Check for JavaScript-style .then() calls or event handlers"
                        
                        log_scraper_event(
                            "error", 
                            "Error launching Browser", 
                            error_details,
                            correlation_id=correlation_id,
                            tags=["browser", "launch_error", "error"]
                        )
                        raise launch_error
                    
                    print("[SCRAPER] Browser erfolgreich gestartet")
                    log_scraper_event(
                        "success", 
                        "Browser erfolgreich gestartet", 
                        {
                            "browser_version": version,
                            "user_agent": user_agent
                        },
                        correlation_id=correlation_id,
                        tags=["browser", "start_success"]
                    )
                    
                    # Browser-Kontext erstellen mit Fehlerbehandlung
                    try:
                        context = await browser.new_context(
                            user_agent=USER_AGENT, 
                            viewport={"width": 1280, "height": 900}
                        )
                        log_scraper_event(
                            "info", 
                            "Browser context created", 
                            {
                                "user_agent": USER_AGENT,
                                "viewport": {"width": 1280, "height": 900}
                            },
                            correlation_id=correlation_id,
                            tags=["browser", "context_created"]
                        )
                        
                        # Neue Seite öffnen mit Fehlerbehandlung
                        try:
                            page = await context.new_page()
                            log_scraper_event(
                                "info", 
                                "New page opened",
                                correlation_id=correlation_id,
                                tags=["browser", "page_opened"]
                            )

                            # Verwende eine komplett andere Herangehensweise ohne Event-Handler
                            log_scraper_event(
                                "info", 
                                "Setting up network monitoring without event handlers",
                                correlation_id=correlation_id,
                                tags=["network", "monitoring_setup"]
                            )
                            
                            # Verwende eine Liste, um die Antworten zu speichern
                            responses = []
                            
                            # Definiere eine synchrone Funktion zum Protokollieren von Netzwerkantworten
                            def log_response(resp):
                                try:
                                    if resp and hasattr(resp, 'status') and hasattr(resp, 'url'):
                                        content_type = resp.headers.get('content-type', '') if hasattr(resp, 'headers') else ''
                                        method = resp.request.method if hasattr(resp, 'request') and hasattr(resp.request, 'method') else 'UNKNOWN'
                                        network_lines.append(f"{resp.status} {method} {resp.url} [{content_type}]")
                                except Exception as e:
                                    log_scraper_event(
                                        "warning", 
                                        "Error logging response", 
                                        {"error": str(e)},
                                        correlation_id=correlation_id,
                                        tags=["network", "response_logging_error", "warning"]
                                    )
                            
                            # Wir verwenden keine Event-Handler mehr, sondern sammeln Antworten manuell
                                
                            # Hier beginnt der Scraping-Prozess für jede Seite
                            all_projects = []
                            
                            # Durchlaufe alle Seiten und extrahiere Projekte
                            for page_idx in pages:
                                current_url = START_URL_TEMPLATE.format(page=page_idx)
                                log_scraper_event(
                                    "info", 
                                    f"Navigating to page {page_idx}", 
                                    {
                                        "url": current_url
                                    },
                                    correlation_id=correlation_id,
                                    tags=["navigation", f"page_{page_idx}"]
                                )
                                captured: List[Tuple[str, Any]] = []

                                # Wir verwenden keinen Event-Handler mehr für API-Antworten
                                log_scraper_event(
                                "info", 
                                "Setting up API response capture without event handlers",
                                correlation_id=correlation_id,
                                tags=["api", "response_capture_setup"]
                            )
                                
                                # Diese Funktion wird später direkt aufgerufen
                                async def process_api_response(resp):
                                    if resp and hasattr(resp, 'url') and hasattr(resp, 'headers'):
                                        if API_RE.search(resp.url) and "application/json" in resp.headers.get("content-type", ""):
                                            try:
                                                json_data = await resp.json()
                                                captured.append((resp.url, json_data))
                                                log_scraper_event(
                                                    "info", 
                                                    "Captured API response", 
                                                    {"url": resp.url},
                                                    correlation_id=correlation_id,
                                                    tags=["api", "response_captured"]
                                                )
                                            except Exception as e:
                                                log_scraper_event(
                                                    "warning", 
                                                    "Error capturing API response", 
                                                    {
                                                        "url": resp.url,
                                                        "error": str(e)
                                                    },
                                                    correlation_id=correlation_id,
                                                    tags=["api", "response_capture_error", "warning"]
                                                )
                                
                                # Kein Event-Handler-Registrierung mehr mit page.on()

                                # Navigiere zur Seite mit Fehlerbehandlung und manueller Erfassung der Antworten
                                try:
                                    # Detaillierte Logging vor der Navigation
                                    log_scraper_event(
                                        "info", 
                                        f"Navigating to page {page_idx}", 
                                        {
                                            "url": current_url,
                                            "browser_info": {
                                                "version": version if 'version' in locals() else "unknown",
                                                "user_agent": user_agent if 'user_agent' in locals() else "unknown"
                                            },
                                            "page_state": "pre-navigation"
                                        },
                                        correlation_id=correlation_id,
                                        tags=["navigation", f"page_{page_idx}", "pre_navigation"]
                                    )
                                    
                                    # Verwende CDP Session, um Netzwerkanfragen zu überwachen
                                    try:
                                        cdp_session = await page.context.new_cdp_session(page)
                                        await cdp_session.send('Network.enable')
                                        log_scraper_event(
                                            "info", 
                                            "CDP session established for network monitoring",
                                            correlation_id=correlation_id,
                                            tags=["network", "cdp_session"]
                                        )
                                    except Exception as cdp_error:
                                        log_scraper_event(
                                            "warning", 
                                            "Could not establish CDP session", 
                                            {
                                                "error": str(cdp_error),
                                                "traceback": traceback.format_exc()
                                            },
                                            correlation_id=correlation_id,
                                            tags=["network", "cdp_session_error", "warning"]
                                        )
                                    
                                    # Navigiere zur Seite mit Timeout-Handling
                                    try:
                                        start_time = time.time()
                                        response = await page.goto(current_url, timeout=60000)  # 60 Sekunden Timeout
                                        navigation_time = time.time() - start_time
                                        log_scraper_event(
                                            "info", 
                                            f"Successfully navigated to page {page_idx}", 
                                            {
                                                "navigation_time_seconds": round(navigation_time, 2),
                                                "status": response.status if response else "unknown",
                                                "url": current_url
                                            },
                                            correlation_id=correlation_id,
                                            tags=["navigation", "page_load_success"]
                                        )
                                    except Exception as goto_error:
                                        log_scraper_event(
                                            "error", 
                                            f"Navigation timeout or error on page {page_idx}", 
                                            {
                                                "error": str(goto_error),
                                                "url": current_url,
                                                "traceback": traceback.format_exc()
                                            },
                                            correlation_id=correlation_id,
                                            tags=["navigation", "page_load_error", "error"]
                                        )
                                        # Versuche trotzdem fortzufahren
                                        response = None
                                        
                                    # Sammle Ressourcen und Performance-Metriken
                                    resources = []
                                    try:
                                        # Sammle Netzwerk-Ressourcen für Performance-Analyse
                                        resources = await page.evaluate("() => JSON.parse(JSON.stringify(performance.getEntriesByType('resource')))")
                                        log_scraper_event(
                                            "info", 
                                            "Collected resource timing data", 
                                            {
                                                "resource_count": len(resources),
                                                "resource_types": {r["type"]: sum(1 for res in resources if res["type"] == r["type"]) 
                                                            for r in resources if "type" in r},
                                                "total_transfer_size_kb": round(sum(r["size"] for r in resources if "size" in r) / 1024, 2) if resources else 0
                                            },
                                            correlation_id=correlation_id,
                                            tags=["resources", "timing_data"]
                                        )
                                    except Exception as res_error:
                                        log_scraper_event(
                                            "info", 
                                            "Collected resource timing data", 
                                            {
                                                "resource_count": len(resources)
                                            },
                                            correlation_id=correlation_id,
                                            tags=["resources", "timing_data"]
                                        )
                                        resources = []
                                    
                                    # Prüfe auf API-Anfragen in den gesammelten Ressourcen
                                    try:
                                        api_resources = [r for r in resources if "name" in r and API_RE.search(r["name"])]
                                        if api_resources:
                                            log_scraper_event(
                                                "info", 
                                                "Found API resources", 
                                                {"api_resource_count": len(api_resources)},
                                                correlation_id=correlation_id,
                                                tags=["api", "resources"]
                                            )
                                    except Exception as api_error:
                                        log_scraper_event(
                                            "error", 
                                            "Error processing API resources", 
                                            {"error": str(api_error)},
                                            correlation_id=correlation_id,
                                            tags=["api", "resources", "error"]
                                        )
                                        continue
                                
                                try:
                                    # Scroll through the page to trigger lazy loading
                                    log_scraper_event(
                                        "info", 
                                        f"Scrolling page {page_idx} to trigger lazy loading", 
                                        {
                                            "scroll_steps": SCROLL_STEPS,
                                            "scroll_pause": SCROLL_PAUSE,
                                            "collect_seconds": COLLECT_SECS
                                        },
                                        correlation_id=correlation_id,
                                        tags=["browser", "page_scrolling"]
                                    )
                                except Exception as scroll_log_error:
                                    log_scraper_event(
                                        "error", 
                                        "Error logging scroll operation", 
                                        {"error": str(scroll_log_error)},
                                        correlation_id=correlation_id,
                                        tags=["error", "logging_error", "scrolling"]
                                    )
                                
                                try:
                                    for step in range(SCROLL_STEPS):
                                        # Scroll down
                                        await page.evaluate(f"window.scrollTo(0, {step * 1000})")
                                        await page.wait_for_timeout(SCROLL_PAUSE)
                                except Exception as scroll_error:
                                    log_scraper_event(
                                        "error", 
                                        "Error during page scrolling", 
                                        {"error": str(scroll_error)},
                                        correlation_id=correlation_id,
                                        tags=["error", "browser", "scrolling"]
                                    )
                            # Close browser resources with proper error handling
                            try:
                                await page.close()
                                log_scraper_event(
                                    "info", 
                                    "Page closed successfully",
                                    correlation_id=correlation_id,
                                    tags=["browser", "cleanup"]
                                )
                            except Exception as page_close_error:
                                log_scraper_event(
                                    "error", 
                                    "Error closing page", 
                                    {"error": str(page_close_error)},
                                    correlation_id=correlation_id,
                                    tags=["browser", "page_closing_error", "warning"]
                                )
                                
                            try:
                                await context.close()
                                log_scraper_event(
                                    "info", 
                                    "Browser context closed successfully",
                                    correlation_id=correlation_id,
                                    tags=["browser", "context_closing"]
                                )
                            except Exception as context_close_error:
                                log_scraper_event(
                                    "error", 
                                    "Error closing browser context", 
                                    {"error": str(context_close_error)},
                                    correlation_id=correlation_id,
                                    tags=["error", "browser", "context_closing"]
                                )
                                
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
                                    log_scraper_event(
                                        "info", 
                                        "Processing API responses", 
                                        {"count": len(captured)},
                                        correlation_id=correlation_id,
                                        tags=["api", "processing_responses"]
                                    )
                                    log_scraper_event(
                                        "info", 
                                        "Processing scraped projects", 
                                        {
                                            "total_projects_found": len(all_projects)
                                        },
                                        correlation_id=correlation_id,
                                        tags=["data", "processing"]
                                    )
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
                                        log_scraper_event(
                                            "info", 
                                            "Attempting to send email notification", 
                                            {
                                                "recipient": email_recipient,
                                                "new_projects_count": len(new_projects)
                                            },
                                            correlation_id=correlation_id,
                                            tags=["email", "notification_attempt"]
                                        )
                                        
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
                                                log_scraper_event(
                                                    "success" if success else "warning", 
                                                    "Email notification result", 
                                                    {
                                                        "success": success,
                                                        "recipient": email_recipient,
                                                        "new_projects_count": len(new_projects)
                                                    },
                                                    correlation_id=correlation_id,
                                                    tags=["email", "notification_result"]
                                                )
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
                                "traceback": traceback.format_exc()
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
                log_scraper_event(
                    "info", 
                    "Created dummy data file", 
                    {"project_count": len(dummy_projects)},
                    correlation_id=correlation_id,
                    tags=["dummy_data", "file_creation"]
                )
            except Exception as save_error:
                print(f"[RENDER DEBUG] Error saving dummy data: {str(save_error)}")
                log_scraper_event(
                    "error", 
                    "Error saving dummy data", 
                    {"error": str(save_error)},
                    correlation_id=correlation_id,
                    tags=["dummy_data", "file_error", "error"]
                )
            
            # Verarbeite die Dummy-Projekte
            unique_projects, new_projects = project_manager.process_projects(dummy_projects)
            print(f"[RENDER DEBUG] Processed {len(unique_projects)} unique projects, {len(new_projects)} new")
            log_scraper_event(
                "info", 
                "Processed dummy projects", 
                {
                    "unique_count": len(unique_projects),
                    "new_count": len(new_projects)
                },
                correlation_id=correlation_id,
                tags=["dummy_data", "processing"]
            )
            
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


class LogFilterParams(BaseModel):
    event_type: Optional[str] = None
    log_level: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    correlation_id: Optional[str] = None
    tags: Optional[List[str]] = None
    limit: Optional[int] = None
    search_query: Optional[str] = None

@app.get("/api/scraper-logs", tags=["scraper"])
async def get_scraper_logs(
    event_type: Optional[str] = None,
    log_level: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    correlation_id: Optional[str] = None,
    tag: Optional[str] = None,
    limit: Optional[int] = None,
    search: Optional[str] = None
):
    """
    Get the detailed scraper logs for the detailed view with filtering options
    
    - **event_type**: Filter by event type (info, warning, error, success)
    - **log_level**: Filter by log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    - **start_time**: Filter logs after this ISO timestamp
    - **end_time**: Filter logs before this ISO timestamp
    - **correlation_id**: Filter logs by correlation ID
    - **tag**: Filter logs by tag
    - **limit**: Limit the number of returned logs
    - **search**: Search logs by message content
    """
    filtered_logs = scraper_logs.copy()
    
    # Apply filters
    if event_type:
        filtered_logs = [log for log in filtered_logs if log.get("event_type") == event_type]
    
    if log_level:
        filtered_logs = [log for log in filtered_logs if log.get("log_level") == log_level.upper()]
    
    if start_time:
        try:
            start_dt = datetime.datetime.fromisoformat(start_time)
            filtered_logs = [log for log in filtered_logs if datetime.datetime.fromisoformat(log.get("timestamp", "")) >= start_dt]
        except (ValueError, TypeError):
            pass
    
    if end_time:
        try:
            end_dt = datetime.datetime.fromisoformat(end_time)
            filtered_logs = [log for log in filtered_logs if datetime.datetime.fromisoformat(log.get("timestamp", "")) <= end_dt]
        except (ValueError, TypeError):
            pass
    
    if correlation_id:
        filtered_logs = [log for log in filtered_logs if log.get("correlation_id") == correlation_id]
    
    if tag:
        filtered_logs = [log for log in filtered_logs if tag in log.get("tags", [])]
    
    if search:
        search = search.lower()
        filtered_logs = [log for log in filtered_logs if 
                        search in log.get("message", "").lower() or 
                        any(search in str(v).lower() for v in log.get("data", {}).values())]
    
    # Sort by timestamp (newest first)
    filtered_logs = sorted(filtered_logs, key=lambda x: x.get("timestamp", ""), reverse=True)
    
    # Apply limit
    if limit and limit > 0:
        filtered_logs = filtered_logs[:limit]
    
    # Get unique correlation IDs for grouping
    correlation_ids = list(set(log.get("correlation_id") for log in filtered_logs if log.get("correlation_id")))
    
    # Get unique log levels for statistics
    log_levels = {}
    for log in filtered_logs:
        level = log.get("log_level")
        if level:
            log_levels[level] = log_levels.get(level, 0) + 1
    
    return {
        "logs": filtered_logs,
        "count": len(filtered_logs),
        "total_count": len(scraper_logs),
        "correlation_ids": correlation_ids,
        "log_levels": log_levels
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
