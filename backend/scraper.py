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
MAX_LOG_ENTRIES = 100  # Maximale Anzahl der Log-Einträge

def save_logs_to_file():
    """
    Speichert die Scraper-Logs in einer Datei.
    """
    global scraper_logs
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

# Global variable to track current scrape session
current_scrape_session = None

def analyze_error_from_traceback(traceback_str):
    """Analysiert einen Stack-Trace und extrahiert nützliche Fehlerinformationen."""
    if not traceback_str or traceback_str == "No traceback available":
        return {"category": "unknown", "severity": "medium"}
    
    analysis = {
        "category": "unknown",
        "severity": "medium",
        "common_causes": [],
        "suggested_actions": []
    }
    
    traceback_lower = traceback_str.lower()
    
    # Browser/Playwright Fehler
    if any(keyword in traceback_lower for keyword in ["playwright", "browser", "chromium", "page.goto"]):
        analysis["category"] = "browser"
        analysis["severity"] = "high"
        analysis["common_causes"] = [
            "Browser nicht installiert oder nicht erreichbar",
            "Netzwerkprobleme beim Laden der Seite",
            "Timeout beim Warten auf Seitenelemente",
            "Ungültige Selektoren oder veränderte Website-Struktur"
        ]
        analysis["suggested_actions"] = [
            "Browser-Installation überprüfen",
            "Timeout-Werte erhöhen",
            "Headless-Modus testen",
            "Netzwerkverbindung prüfen"
        ]
    
    # Netzwerk-Fehler
    elif any(keyword in traceback_lower for keyword in ["connectionerror", "timeout", "httperror", "network"]):
        analysis["category"] = "network"
        analysis["severity"] = "high"
        analysis["common_causes"] = [
            "Keine Internetverbindung",
            "Ziel-Website nicht erreichbar",
            "Firewall blockiert Zugriff",
            "Rate-Limiting oder IP-Blocking"
        ]
        analysis["suggested_actions"] = [
            "Internetverbindung testen",
            "Website-Verfügbarkeit prüfen",
            "VPN oder andere IP verwenden",
            "Scraping-Geschwindigkeit reduzieren"
        ]
    
    # Speicher-Fehler
    elif any(keyword in traceback_lower for keyword in ["memoryerror", "out of memory", "cannot allocate"]):
        analysis["category"] = "memory"
        analysis["severity"] = "critical"
        analysis["common_causes"] = [
            "Unzureichender Arbeitsspeicher",
            "Memory Leak im Code",
            "Zu viele gleichzeitige Browser-Instanzen"
        ]
        analysis["suggested_actions"] = [
            "Server-Ressourcen erhöhen", 
            "Browser-Instanzen begrenzen",
            "Memory-Usage monitoring aktivieren",
            "Garbage Collection optimieren"
        ]
    
    # Datei-/Pfad-Fehler
    elif any(keyword in traceback_lower for keyword in ["filenotfounderror", "permissionerror", "no such file"]):
        analysis["category"] = "filesystem"
        analysis["severity"] = "medium"
        analysis["common_causes"] = [
            "Datei oder Verzeichnis existiert nicht",
            "Keine Berechtigung für Dateizugriff",
            "Falsche Pfadangabe",
            "Datei von anderem Prozess gesperrt"
        ]
        analysis["suggested_actions"] = [
            "Dateipfade überprüfen",
            "Berechtigungen anpassen",
            "Verzeichnisse erstellen falls nötig",
            "Concurrent Access vermeiden"
        ]
    
    # JSON/Parsing-Fehler
    elif any(keyword in traceback_lower for keyword in ["jsondecodeerror", "invalid json", "parsing error"]):
        analysis["category"] = "parsing"
        analysis["severity"] = "medium"
        analysis["common_causes"] = [
            "Unvollständige oder korrupte JSON-Daten",
            "Unerwartetes Datenformat",
            "Encoding-Probleme",
            "Leere oder fehlerhafte API-Antworten"
        ]
        analysis["suggested_actions"] = [
            "JSON-Daten validieren",
            "Error-Handling für leere Antworten",
            "Encoding explizit setzen",
            "Datenformat vor Parsing prüfen"
        ]
    
    return analysis

def aggregate_log_statistics():
    """Erstellt aggregierte Statistiken aus den Log-Einträgen."""
    global scraper_logs
    
    # Filter out None entries first
    scraper_logs = [log for log in scraper_logs if log is not None and isinstance(log, dict)]
    
    if not scraper_logs:
        return {}
    
    stats = {
        "total_entries": len(scraper_logs),
        "entries_by_type": {},
        "entries_by_level": {},
        "error_categories": {},
        "performance_summary": {
            "avg_memory_mb": 0,
            "peak_memory_mb": 0,
            "avg_cpu_percent": 0,
            "peak_cpu_percent": 0
        },
        "session_summary": {},
        "recent_critical_errors": [],
        "diagnostic_insights": []
    }
    
    memory_values = []
    cpu_values = []
    
    for log_entry in scraper_logs:
        # Skip None entries
        if not log_entry:
            continue
            
        # Event Type Statistiken
        event_type = log_entry.get("event_type", "unknown")
        stats["entries_by_type"][event_type] = stats["entries_by_type"].get(event_type, 0) + 1
        
        # Log Level Statistiken  
        log_level = log_entry.get("log_level", "INFO")
        stats["entries_by_level"][log_level] = stats["entries_by_level"].get(log_level, 0) + 1
        
        # Error Category Analyse
        if log_entry.get("data", {}).get("error_category"):
            category = log_entry["data"]["error_category"]
            stats["error_categories"][category] = stats["error_categories"].get(category, 0) + 1
        
        # Performance Daten sammeln
        perf_info = log_entry.get("data", {}).get("performance_info", {})
        if isinstance(perf_info, dict):
            if "memory_rss_mb" in perf_info:
                memory_values.append(perf_info["memory_rss_mb"])
            if "cpu_percent" in perf_info:
                cpu_values.append(perf_info["cpu_percent"])
        
        # Session Tracking
        session_id = log_entry.get("session_id")
        if session_id:
            if session_id not in stats["session_summary"]:
                stats["session_summary"][session_id] = {
                    "entry_count": 0,
                    "error_count": 0,
                    "start_time": log_entry.get("timestamp"),
                    "end_time": log_entry.get("timestamp")
                }
            stats["session_summary"][session_id]["entry_count"] += 1
            stats["session_summary"][session_id]["end_time"] = log_entry.get("timestamp")
            if event_type in ["error", "critical"]:
                stats["session_summary"][session_id]["error_count"] += 1
        
        # Kritische Fehler der letzten Zeit sammeln
        if event_type in ["error", "critical"]:
            log_time = log_entry.get("timestamp")
            stats["recent_critical_errors"].append({
                "timestamp": log_time,
                "message": log_entry.get("message", ""),
                "category": log_entry.get("data", {}).get("error_category", "unknown"),
                "session_id": session_id
            })
    
    # Performance Zusammenfassung berechnen
    if memory_values:
        stats["performance_summary"]["avg_memory_mb"] = round(sum(memory_values) / len(memory_values), 2)
        stats["performance_summary"]["peak_memory_mb"] = round(max(memory_values), 2)
    
    if cpu_values:
        stats["performance_summary"]["avg_cpu_percent"] = round(sum(cpu_values) / len(cpu_values), 2)
        stats["performance_summary"]["peak_cpu_percent"] = round(max(cpu_values), 2)
    
    # Nur die letzten 10 kritischen Fehler behalten
    stats["recent_critical_errors"] = stats["recent_critical_errors"][-10:]
    
    # Diagnostische Insights generieren
    if stats["entries_by_type"].get("error", 0) > 5:
        stats["diagnostic_insights"].append(
            "Hohe Anzahl von Fehlern erkannt - System-Check empfohlen"
        )
    
    if stats["performance_summary"]["peak_memory_mb"] > 500:
        stats["diagnostic_insights"].append(
            "Hoher Speicherverbrauch erkannt - Memory-Optimierung empfohlen"
        )
    
    if len(stats["error_categories"]) > 3:
        stats["diagnostic_insights"].append(
            "Verschiedene Fehlerkategorien - Umfassende Diagnose erforderlich"
        )
    
    return stats

def log_scraper_event(event_type, message, data=None, log_level=None, correlation_id=None, tags=None, session_id=None):
    """
    Fügt einen neuen Log-Eintrag zu den Scraper-Logs hinzu.
    
    Args:
        event_type (str): Art des Events (info, warning, error, success)
        message (str): Nachricht für das Log
        data (dict, optional): Zusätzliche Daten zum Event
        log_level (str, optional): Log-Level (debug, info, warning, error, critical)
        correlation_id (str, optional): ID zur Korrelation zusammengehöriger Log-Einträge
        tags (list, optional): Tags zur Kategorisierung des Log-Eintrags
        session_id (str, optional): Session ID für die aktuelle Scrape-Session
    """
    global scraper_logs, current_scrape_session
    
    if data is None:
        data = {}
    
    # Füge zusätzliche Kontextinformationen hinzu
    # Use a more compatible approach for timezone handling
    try:
        timestamp = datetime.datetime.now().replace(microsecond=0).isoformat() + 'Z'  # UTC format
    except Exception as e:
        print(f"Error formatting timestamp: {str(e)}")
        timestamp = datetime.datetime.now().isoformat()  # Fallback
    
    # Verwende die aktuelle Session-ID wenn verfügbar
    if session_id is None and current_scrape_session:
        session_id = current_scrape_session
    
    # Füge Umgebungsinformationen hinzu
    env_info = {
        "is_cloud": IS_CLOUD_ENV,
        "use_real_scraper": USE_REAL_SCRAPER,
        "headless": HEADLESS,
        "session_id": session_id
    }
    
    # Erweitere die Daten für bessere Diagnose
    enhanced_data = data.copy()
    if session_id:
        enhanced_data["session_id"] = session_id
    
    # Füge Performance-Informationen hinzu
    try:
        import psutil
        process = psutil.Process()
        
        # CPU und Memory Information
        cpu_percent = process.cpu_percent()
        memory_info = process.memory_info()
        
        enhanced_data["performance_info"] = {
            "cpu_percent": cpu_percent,
            "memory_rss_mb": round(memory_info.rss / 1024 / 1024, 2),
            "memory_vms_mb": round(memory_info.vms / 1024 / 1024, 2),
            "memory_percent": process.memory_percent(),
            "num_threads": process.num_threads(),
            "create_time": process.create_time()
        }
        
        # System-weite Informationen bei kritischen Events
        if event_type in ["error", "critical"]:
            system_memory = psutil.virtual_memory()
            system_disk = psutil.disk_usage('/')
            enhanced_data["system_info"] = {
                "total_memory_gb": round(system_memory.total / 1024 / 1024 / 1024, 2),
                "available_memory_gb": round(system_memory.available / 1024 / 1024 / 1024, 2),
                "memory_usage_percent": system_memory.percent,
                "disk_usage_percent": system_disk.percent,
                "cpu_count": psutil.cpu_count(),
                "load_average": psutil.getloadavg() if hasattr(psutil, 'getloadavg') else None
            }
    except ImportError:
        enhanced_data["performance_info"] = "psutil not available"
    except Exception as e:
        enhanced_data["performance_info"] = f"Error getting performance info: {str(e)}"
    
    # Füge Stack-Trace für Fehler hinzu
    if event_type in ["error", "warning", "critical"]:
        if "traceback" not in enhanced_data:
            trace = traceback.format_exc()
            if trace != "NoneType: None\n":
                enhanced_data["traceback"] = trace
                # Analysiere den Stack-Trace für häufige Fehlertypen
                enhanced_data["error_analysis"] = analyze_error_from_traceback(trace)
            else:
                enhanced_data["traceback"] = "No traceback available"
        
        # Füge Browser-spezifische Diagnose hinzu
        if "playwright" in message.lower() or "browser" in message.lower():
            enhanced_data["error_category"] = "browser"
            enhanced_data["diagnostic_tips"] = [
                "Check browser installation",
                "Verify network connectivity",
                "Check if headless mode is appropriate",
                "Verify timeout settings"
            ]
        elif "network" in message.lower() or "timeout" in message.lower():
            enhanced_data["error_category"] = "network"
            enhanced_data["diagnostic_tips"] = [
                "Check internet connection",
                "Verify target website availability",
                "Consider increasing timeout values",
                "Check for rate limiting"
            ]
        elif "permission" in message.lower() or "access" in message.lower():
            enhanced_data["error_category"] = "permission"
            enhanced_data["diagnostic_tips"] = [
                "Check file/directory permissions",
                "Verify user access rights",
                "Check if files are locked by other processes"
            ]
    
    # Map event_type to log_level if not provided
    if log_level is None:
        log_level_map = {
            "info": "INFO",
            "warning": "WARNING",
            "error": "ERROR",
            "critical": "CRITICAL",
            "success": "INFO"
        }
        log_level = log_level_map.get(event_type, "INFO")
    else:
        log_level = log_level.upper()
    
    # Generate correlation ID if not provided - verwende Session-ID als Basis
    if correlation_id is None:
        if session_id:
            correlation_id = f"{session_id}-{uuid.uuid4().hex[:8]}"
        else:
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
        "session_id": session_id,
        "tags": tags or [],
        "performance": performance_metrics
    }
    
    # Ausgabe in der Konsole für bessere Sichtbarkeit mit Session-ID
    session_prefix = f"[{session_id[:8]}]" if session_id else ""
    print(f"[SCRAPER LOG]{session_prefix} [{event_type.upper()}] {message}")
    if event_type == "error":
        print(f"[SCRAPER ERROR DETAILS]{session_prefix} {json.dumps(enhanced_data, default=str)}")
    
    # Sorge dafür, dass die Logs sofort sichtbar sind
    sys.stdout.flush()
    if event_type == "error":
        sys.stderr.flush()
    
    scraper_logs.append(log_entry)
    
    # Begrenze die Anzahl der Logs
    if len(scraper_logs) > MAX_LOG_ENTRIES:
        scraper_logs = scraper_logs[-MAX_LOG_ENTRIES:]
    
    # Speichere die Logs in einer Datei
    save_logs_to_file()
    
    # Gib den Log-Eintrag zurück für weitere Verarbeitung
    return log_entry

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
ARCHIVE_JSON = DATA_DIR / "archive_projects.json"
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

# Match API calls for project data (updated for new GULP API structure)
API_RE = re.compile(r'/rest/internal/projects/search')
PROJ_KEY_CANDIDATES = {"title", "jobTitle"}

# Globale Variablen für den Scraper-Status
is_scraping = False
last_scrape_time = None
email_notification_enabled = True
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


async def scrape_gulp_real(correlation_id):
    """Real GULP scraper using the new API structure"""
    captured_projects = []
    
    async def process_api_response(response):
        """Process the new GULP API response format"""
        if response and API_RE.search(response.url) and response.status == 200:
            try:
                data = await response.json()
                log_scraper_event(
                    "info",
                    "API Response received",
                    {
                        "url": response.url,
                        "status": response.status,
                        "data_keys": list(data.keys()) if isinstance(data, dict) else "not_dict"
                    },
                    correlation_id=correlation_id,
                    tags=["api", "response_received"]
                )
                
                # New API structure: {'totalCount': int, 'projects': [...]}
                if isinstance(data, dict) and 'projects' in data:
                    projects = data['projects']
                    log_scraper_event(
                        "info",
                        f"Found {len(projects)} projects in API response",
                        {"projects_count": len(projects)},
                        correlation_id=correlation_id,
                        tags=["projects", "api_data"]
                    )
                    captured_projects.extend(projects)
                
                return data
            except Exception as e:
                log_scraper_event(
                    "error",
                    "Error processing API response",
                    {
                        "url": response.url,
                        "error": str(e)
                    },
                    correlation_id=correlation_id,
                    tags=["api", "error", "response_processing"]
                )
        return None
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=USER_AGENT)
        page = await context.new_page()
        
        # Handle API responses
        page.on("response", process_api_response)
        
        try:
            log_scraper_event(
                "info",
                "Loading GULP project page",
                {"url": "https://www.gulp.de/gulp2/g/projekte"},
                correlation_id=correlation_id,
                tags=["page_load", "navigation"]
            )
            
            # Try to load the page (with timeout handling)
            try:
                await page.goto("https://www.gulp.de/gulp2/g/projekte", timeout=15000, wait_until="domcontentloaded")
                log_scraper_event(
                    "info",
                    "Page loaded successfully",
                    {"current_url": page.url},
                    correlation_id=correlation_id,
                    tags=["page_load", "success"]
                )
                
                # Wait for API calls
                await asyncio.sleep(5)
                
                # Try to scroll to load more projects
                try:
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await asyncio.sleep(2)
                    log_scraper_event(
                        "info",
                        "Scrolled page to load more projects",
                        {},
                        correlation_id=correlation_id,
                        tags=["scroll", "interaction"]
                    )
                except Exception as e:
                    log_scraper_event(
                        "warning",
                        "Scroll error (not critical)",
                        {"error": str(e)},
                        correlation_id=correlation_id,
                        tags=["scroll", "warning"]
                    )
                
            except Exception as navigation_error:
                log_scraper_event(
                    "warning",
                    "Page load timeout/error - continuing with API capture",
                    {
                        "error": str(navigation_error),
                        "error_type": type(navigation_error).__name__
                    },
                    correlation_id=correlation_id,
                    tags=["page_load", "timeout", "warning"]
                )
            
        finally:
            await browser.close()
    
    log_scraper_event(
        "info",
        "Scraper completed",
        {"total_projects": len(captured_projects)},
        correlation_id=correlation_id,
        tags=["scraper", "completed"]
    )
    
    return captured_projects


def scrape_gulp(pages=[1], correlation_id=None):
    """Main scraping function - now with integrated real scraper"""
    if correlation_id is None:
        correlation_id = str(uuid.uuid4())
    
    log_scraper_event(
        "info", 
        "Starting GULP scraper", 
        {
            "pages": pages,
            "correlation_id": correlation_id,
            "use_real_scraper": USE_REAL_SCRAPER,
            "environment": "Cloud" if IS_CLOUD_ENV else "Local"
        },
        correlation_id=correlation_id,
        tags=["scraper", "startup"]
    )
    
    try:
        if USE_REAL_SCRAPER:
            # Use the real scraper
            log_scraper_event(
                "info",
                "Using real GULP scraper with new API",
                {"api_pattern": API_RE.pattern},
                correlation_id=correlation_id,
                tags=["scraper", "real", "api"]
            )
            
            # Run the async scraper function
            # Prüfe, ob bereits ein Event Loop läuft (z.B. in FastAPI)
            try:
                # Versuche, den aktuellen Loop zu bekommen
                current_loop = asyncio.get_running_loop()
                # Wenn ein Loop läuft, verwende asyncio.create_task in einem neuen Thread
                import concurrent.futures
                import threading
                
                def run_scraper_in_new_loop():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(scrape_gulp_real(correlation_id))
                    finally:
                        new_loop.close()
                
                # Führe Scraper in separatem Thread aus
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(run_scraper_in_new_loop)
                    all_projects = future.result(timeout=300)  # 5 Minuten Timeout
                    
            except RuntimeError:
                # Kein Event Loop läuft, wir können einen neuen erstellen
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    all_projects = loop.run_until_complete(scrape_gulp_real(correlation_id))
                finally:
                    loop.close()
            
            if all_projects:
                log_scraper_event(
                    "success",
                    "Real scraper completed successfully",
                    {
                        "projects_found": len(all_projects),
                        "first_project_id": all_projects[0].get("id", "unknown") if all_projects else None
                    },
                    correlation_id=correlation_id,
                    tags=["scraper", "success", "real_data"]
                )
                return all_projects
            else:
                log_scraper_event(
                    "warning",
                    "Real scraper returned no projects - using fallback",
                    {},
                    correlation_id=correlation_id,
                    tags=["scraper", "fallback", "no_data"]
                )
        else:
            log_scraper_event(
                "info",
                "Real scraper disabled, using fallback data",
                {"reason": "USE_REAL_SCRAPER=False"},
                correlation_id=correlation_id,
                tags=["scraper", "disabled", "fallback"]
            )
        
        # Fallback projects if real scraper disabled or failed
        fallback_projects = [
            {
                "id": "FALLBACK001",
                "title": "Senior Frontend Developer",
                "description": "React.js Entwicklung für E-Commerce Platform",
                "location": "Berlin",
                "companyName": "Tech Startup Berlin",
                "datePosted": datetime.datetime.now().isoformat(),
                "type": "GULP_PROJECT"
            },
            {
                "id": "FALLBACK002",
                "title": "Full Stack Developer", 
                "description": "Node.js und Vue.js Entwicklung",
                "location": "München",
                "companyName": "Innovation GmbH",
                "datePosted": datetime.datetime.now().isoformat(),
                "type": "GULP_PROJECT"
            },
            {
                "id": "FALLBACK003",
                "title": "DevOps Engineer",
                "description": "AWS Cloud Infrastructure",
                "location": "Remote",
                "companyName": "Cloud Solutions AG",
                "datePosted": datetime.datetime.now().isoformat(),
                "type": "GULP_PROJECT"
            }
        ]

        return fallback_projects
        
    except Exception as main_error:
        log_scraper_event(
            "error",
            "Critical error in scraper function",
            {
                "error": str(main_error),
                "error_type": type(main_error).__name__,
                "traceback": traceback.format_exc()
            },
            correlation_id=correlation_id,
            tags=["scraper", "critical_error"]
        )
        
        # Return empty list on critical error
        return []




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
    correlation_id = str(uuid.uuid4())[:8]
    
    try:
        print(f"\n[ARCHIVE API {correlation_id}] Archive projects request - search: {search}, location: {location}, remote: {remote}, page: {page}, limit: {limit}")
        print(f"[ARCHIVE API {correlation_id}] Environment: {'Render' if os.environ.get('RENDER') else 'Local'}")
        sys.stdout.flush()
        
        # Check file existence
        data_dir = Path("data")
        archive_file = data_dir / "archive_projects.json"
        recent_file = data_dir / "recent_projects.json"
        raw_file = data_dir / "projects.json"
        
        print(f"[ARCHIVE API {correlation_id}] File status - archive: {archive_file.exists()}, recent: {recent_file.exists()}, raw: {raw_file.exists()}")
        sys.stdout.flush()
        
        # Get archived projects from the project manager
        projects, total = project_manager.get_projects(
            search=search, 
            location=location, 
            remote=remote, 
            page=page, 
            limit=limit, 
            include_new_only=False,
            archived=True,
            show_all=False
        )
        
        print(f"[ARCHIVE API {correlation_id}] Retrieved {len(projects)} projects out of {total} total archived projects")
        sys.stdout.flush()
        
        # Calculate pagination
        total_pages = (total + limit - 1) // limit if limit > 0 else 1
        
        result = {
            "projects": projects,
            "total": total,
            "page": page,
            "limit": limit,
            "type": "archive",
            "lastScrape": last_scrape_time
        }
        
        print(f"[ARCHIVE API {correlation_id}] Success - returning {len(projects)} projects")
        sys.stdout.flush()
        
        return result
        
    except Exception as e:
        error_msg = f"Error retrieving archived projects: {str(e)}"
        print(f"[ARCHIVE API {correlation_id}] ERROR: {error_msg}")
        print(f"[ARCHIVE API {correlation_id}] Traceback: {traceback.format_exc()}")
        sys.stderr.flush()
        
        return JSONResponse(
            status_code=500,
            content={
                "error": error_msg,
                "correlation_id": correlation_id,
                "type": "archive_error"
            }
        )


@app.get("/projects/{project_id}")
async def get_project(project_id: str):
    """Get a specific project by ID."""
    correlation_id = str(uuid.uuid4())[:8]
    
    try:
        # Log the request start
        log_scraper_event(
            "info", 
            "Project details request received", 
            {
                "project_id": project_id,
                "correlation_id": correlation_id,
                "is_cloud_env": IS_CLOUD_ENV,
                "output_file_exists": OUTPUT_JSON.exists()
            },
            correlation_id=correlation_id,
            tags=["project_details", "api_request"]
        )
        print(f"[PROJECT API] Fetching project details for ID: {project_id} (correlation: {correlation_id})")
        sys.stdout.flush()
        
        if not OUTPUT_JSON.exists():
            log_scraper_event(
                "warning", 
                "No project data file available", 
                {
                    "project_id": project_id,
                    "correlation_id": correlation_id,
                    "output_file_path": str(OUTPUT_JSON),
                    "suggestion": "Try triggering a scrape first"
                },
                correlation_id=correlation_id,
                tags=["project_details", "missing_data"]
            )
            print(f"[PROJECT API ERROR] No data file at {OUTPUT_JSON}")
            sys.stderr.flush()
            return JSONResponse(
                status_code=404,
                content={"error": "No project data available. Try triggering a scrape first."}
            )
            
        # Read the projects from the JSON file
        try:
            projects_data = OUTPUT_JSON.read_text(encoding="utf-8")
            projects = json.loads(projects_data)
            
            log_scraper_event(
                "info", 
                "Project data loaded successfully", 
                {
                    "project_id": project_id,
                    "correlation_id": correlation_id,
                    "total_projects": len(projects),
                    "file_size_bytes": len(projects_data)
                },
                correlation_id=correlation_id,
                tags=["project_details", "data_loaded"]
            )
            print(f"[PROJECT API] Loaded {len(projects)} projects from data file")
            sys.stdout.flush()
            
        except json.JSONDecodeError as json_error:
            log_scraper_event(
                "error", 
                "Failed to parse project data JSON", 
                {
                    "project_id": project_id,
                    "correlation_id": correlation_id,
                    "json_error": str(json_error),
                    "file_path": str(OUTPUT_JSON)
                },
                correlation_id=correlation_id,
                tags=["project_details", "json_error"]
            )
            print(f"[PROJECT API ERROR] JSON parse error: {str(json_error)}")
            sys.stderr.flush()
            return JSONResponse(
                status_code=500,
                content={"error": f"Error parsing project data: {str(json_error)}"}
            )
        
        # Find the project with the given ID
        project = next((p for p in projects if p.get("id") == project_id), None)
        
        if not project:
            # Project not found in current data, try archive
            log_scraper_event(
                "info", 
                "Project not found in current data, searching archive", 
                {
                    "requested_project_id": project_id,
                    "correlation_id": correlation_id,
                    "current_projects_count": len(projects),
                    "archive_file_exists": ARCHIVE_JSON.exists()
                },
                correlation_id=correlation_id,
                tags=["project_details", "archive_search"]
            )
            print(f"[PROJECT API] Project {project_id} not in current data, checking archive...")
            sys.stdout.flush()
            
            # Try to find in archive
            if ARCHIVE_JSON.exists():
                try:
                    archive_data = ARCHIVE_JSON.read_text(encoding="utf-8")
                    archive_projects = json.loads(archive_data)
                    
                    # Find project in archive
                    archived_project = next((p for p in archive_projects if p.get("id") == project_id), None)
                    
                    if archived_project:
                        log_scraper_event(
                            "success", 
                            "Project found in archive", 
                            {
                                "project_id": project_id,
                                "correlation_id": correlation_id,
                                "project_title": archived_project.get("title", "Unknown"),
                                "archive_projects_count": len(archive_projects),
                                "is_archived": True
                            },
                            correlation_id=correlation_id,
                            tags=["project_details", "archive_found", "success"]
                        )
                        print(f"[PROJECT API SUCCESS] Found archived project: {archived_project.get('title', 'Unknown')}")
                        sys.stdout.flush()
                        
                        # Add metadata to indicate this is archived
                        archived_project["_isArchived"] = True
                        archived_project["_archivedNotice"] = "Dieses Projekt befindet sich im Archiv und ist möglicherweise nicht mehr aktuell."
                        
                        return archived_project
                    else:
                        log_scraper_event(
                            "info", 
                            "Project not found in archive either", 
                            {
                                "project_id": project_id,
                                "correlation_id": correlation_id,
                                "archive_projects_count": len(archive_projects)
                            },
                            correlation_id=correlation_id,
                            tags=["project_details", "archive_not_found"]
                        )
                        print(f"[PROJECT API] Project {project_id} not found in archive ({len(archive_projects)} archived projects)")
                        
                except json.JSONDecodeError as archive_json_error:
                    log_scraper_event(
                        "error", 
                        "Failed to parse archive JSON", 
                        {
                            "project_id": project_id,
                            "correlation_id": correlation_id,
                            "json_error": str(archive_json_error),
                            "archive_file_path": str(ARCHIVE_JSON)
                        },
                        correlation_id=correlation_id,
                        tags=["project_details", "archive_json_error"]
                    )
                    print(f"[PROJECT API ERROR] Archive JSON parse error: {str(archive_json_error)}")
                    sys.stderr.flush()
                    
                except Exception as archive_error:
                    log_scraper_event(
                        "error", 
                        "Error reading archive file", 
                        {
                            "project_id": project_id,
                            "correlation_id": correlation_id,
                            "error": str(archive_error),
                            "archive_file_path": str(ARCHIVE_JSON)
                        },
                        correlation_id=correlation_id,
                        tags=["project_details", "archive_error"]
                    )
                    print(f"[PROJECT API ERROR] Archive read error: {str(archive_error)}")
                    sys.stderr.flush()
            else:
                log_scraper_event(
                    "warning", 
                    "Archive file does not exist", 
                    {
                        "project_id": project_id,
                        "correlation_id": correlation_id,
                        "archive_file_path": str(ARCHIVE_JSON)
                    },
                    correlation_id=correlation_id,
                    tags=["project_details", "no_archive"]
                )
                print(f"[PROJECT API] No archive file at {ARCHIVE_JSON}")
                sys.stdout.flush()
            
            # Final not found response with debug info
            available_ids = [p.get("id") for p in projects[:10]]  # First 10 for debugging
            log_scraper_event(
                "warning", 
                "Project not found in current data or archive", 
                {
                    "requested_project_id": project_id,
                    "correlation_id": correlation_id,
                    "total_current_projects": len(projects),
                    "sample_current_ids": available_ids,
                    "project_id_type": type(project_id).__name__,
                    "searched_archive": ARCHIVE_JSON.exists()
                },
                correlation_id=correlation_id,
                tags=["project_details", "final_not_found"]
            )
            print(f"[PROJECT API ERROR] Project {project_id} not found in current ({len(projects)}) or archived projects")
            print(f"[PROJECT API DEBUG] Sample current IDs: {available_ids}")
            sys.stderr.flush()
            return JSONResponse(
                status_code=404,
                content={"error": f"Project with ID {project_id} not found"}
            )
        
        # Log successful project retrieval
        log_scraper_event(
            "success", 
            "Project details retrieved successfully", 
            {
                "project_id": project_id,
                "correlation_id": correlation_id,
                "project_title": project.get("title", "Unknown"),
                "project_fields": list(project.keys()) if isinstance(project, dict) else "non-dict"
            },
            correlation_id=correlation_id,
            tags=["project_details", "success"]
        )
        print(f"[PROJECT API SUCCESS] Retrieved project: {project.get('title', 'Unknown')}")
        sys.stdout.flush()
            
        return project
        
    except Exception as e:
        log_scraper_event(
            "error", 
            "Critical error in project details API", 
            {
                "project_id": project_id,
                "correlation_id": correlation_id,
                "error": str(e),
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc()
            },
            correlation_id=correlation_id,
            tags=["project_details", "critical_error", "api_error"]
        )
        print(f"[PROJECT API ERROR] Critical error: {str(e)}")
        print(f"[PROJECT API ERROR] Traceback: {traceback.format_exc()}")
        sys.stderr.flush()
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
    
    # Erweiterte Statistiken für gefilterte Logs hinzufügen
    stats = {
        "total_entries": len(filtered_logs),
        "entries_by_type": {},
        "entries_by_level": {},
        "error_categories": {},
        "recent_errors": []
    }
    
    for log in filtered_logs:
        # Skip None entries
        if not log:
            continue
            
        # Event Type Statistiken
        event_type = log.get("event_type", "unknown")
        stats["entries_by_type"][event_type] = stats["entries_by_type"].get(event_type, 0) + 1
        
        # Log Level Statistiken  
        log_level = log.get("log_level", "INFO")
        stats["entries_by_level"][log_level] = stats["entries_by_level"].get(log_level, 0) + 1
        
        # Error Category Analyse
        if log.get("data", {}) and log.get("data", {}).get("error_category"):
            category = log["data"]["error_category"]
            stats["error_categories"][category] = stats["error_categories"].get(category, 0) + 1
        
        # Letzte Fehler sammeln
        if event_type in ["error", "critical"]:
            stats["recent_errors"].append({
                "timestamp": log.get("timestamp"),
                "message": log.get("message", ""),
                "category": log.get("data", {}).get("error_category", "unknown"),
                "session_id": log.get("session_id")
            })
    
    # Nur die letzten 5 Fehler behalten
    stats["recent_errors"] = stats["recent_errors"][-5:]
    
    return {
        "logs": filtered_logs,
        "count": len(filtered_logs),
        "total_count": len(scraper_logs),
        "correlation_ids": correlation_ids,
        "log_levels": log_levels,
        "statistics": stats
    }


@app.get("/api/scraper-logs/status", tags=["scraper"])
async def get_log_status():
    """Get detailed logging status for monitoring and debugging."""
    try:
        # Clean up None entries from scraper_logs
        global scraper_logs
        scraper_logs = [log for log in scraper_logs if log is not None and isinstance(log, dict)]
        
        log_file_exists = SCRAPER_LOGS_FILE.exists() if SCRAPER_LOGS_FILE else False
        log_file_size = SCRAPER_LOGS_FILE.stat().st_size if log_file_exists else 0
        
        # Calculate recent activity with robust error handling
        now = datetime.datetime.now()
        recent_logs = []
        try:
            if scraper_logs:
                for log in scraper_logs[-10:]:  # Last 10 logs
                    # Skip None entries
                    if not log or not isinstance(log, dict):
                        continue
                    try:
                        timestamp = log.get("timestamp", "")
                        if timestamp:
                            log_time = datetime.datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                            time_diff = (now - log_time).total_seconds()
                            if time_diff < 300:  # Last 5 minutes
                                recent_logs.append({
                                    "timestamp": timestamp,
                                    "event_type": log.get("event_type", "unknown"),
                                    "message": log.get("message", "")
                                })
                    except Exception as e:
                        # Skip logs with invalid timestamps
                        print(f"[ERROR] Error processing log entry: {e}")
                        continue
        except Exception as e:
            print(f"[ERROR] Error processing recent logs: {e}")
            recent_logs = []
        
        # Generiere umfassende Statistiken mit Error-Handling
        try:
            comprehensive_stats = aggregate_log_statistics()
        except Exception as e:
            print(f"[ERROR] Error generating comprehensive stats: {e}")
            comprehensive_stats = {}
        
        # Unique Sessions für bessere Übersicht mit robuster Behandlung
        try:
            unique_sessions = list(set(
                log.get("session_id") for log in scraper_logs 
                if log and isinstance(log, dict) and log.get("session_id")
            ))
        except Exception as e:
            print(f"[ERROR] Error processing unique sessions: {e}")
            unique_sessions = []
        
        # Health Check
        health_indicators = {
            "memory_health": "good",
            "error_rate": "low",
            "performance_health": "good",
            "system_health": "good"
        }
        
        # Bewerte System Health basierend auf Statistiken
        if comprehensive_stats.get("performance_summary", {}).get("peak_memory_mb", 0) > 1000:
            health_indicators["memory_health"] = "critical"
        elif comprehensive_stats.get("performance_summary", {}).get("peak_memory_mb", 0) > 500:
            health_indicators["memory_health"] = "warning"
        
        error_count = comprehensive_stats.get("entries_by_type", {}).get("error", 0)
        total_entries = comprehensive_stats.get("total_entries", 1)
        error_rate = (error_count / total_entries) * 100 if total_entries > 0 else 0
        
        if error_rate > 30:
            health_indicators["error_rate"] = "critical"
        elif error_rate > 15:
            health_indicators["error_rate"] = "warning"
        elif error_rate > 5:
            health_indicators["error_rate"] = "medium"
        
        # System Performance Check
        if comprehensive_stats.get("performance_summary", {}).get("avg_cpu_percent", 0) > 80:
            health_indicators["performance_health"] = "warning"
        
        # Safe response generation with fallback values
        try:
            last_log_timestamp = None
            if scraper_logs:
                for log in reversed(scraper_logs):  # Start from the end
                    if log and isinstance(log, dict) and log.get("timestamp"):
                        last_log_timestamp = log.get("timestamp")
                        break
        except Exception:
            last_log_timestamp = None
        
        try:
            session_logs_count = 0
            if current_scrape_session:
                session_logs_count = len([
                    log for log in scraper_logs 
                    if log and isinstance(log, dict) and log.get("session_id") == current_scrape_session
                ])
        except Exception:
            session_logs_count = 0
            
        return {
            "status": "ok",
            "timestamp": datetime.datetime.now().isoformat(),
            "log_file": {
                "exists": log_file_exists,
                "size_bytes": log_file_size,
                "path": str(SCRAPER_LOGS_FILE) if SCRAPER_LOGS_FILE else None,
                "total_logs": len(scraper_logs) if scraper_logs else 0,
                "memory_logs_count": len(scraper_logs) if scraper_logs else 0,
            },
            "recent_activity": recent_logs or [],
            "environment": {
                "is_cloud": IS_CLOUD_ENV,
                "use_real_scraper": USE_REAL_SCRAPER,
                "headless": HEADLESS,
                "last_log_timestamp": last_log_timestamp,
            },
            "project_manager": {
                "initialized": project_manager is not None,
                "data_dir_exists": DATA_DIR.exists() if DATA_DIR else False
            },
            "scraper_status": {
                "is_scraping": is_scraping,
                "last_scrape_time": last_scrape_time,
            },
            "current_session": {
                "active": current_scrape_session is not None,
                "session_id": current_scrape_session,
                "session_logs_count": session_logs_count
            },
            "comprehensive_statistics": comprehensive_stats or {},
            "session_overview": {
                "total_sessions": len(unique_sessions) if unique_sessions else 0,
                "active_session": current_scrape_session,
                "recent_sessions": unique_sessions[-5:] if unique_sessions and len(unique_sessions) > 5 else (unique_sessions or [])
            },
            "health_indicators": health_indicators or {},
            "system_metrics": {
                "error_rate_percent": round(error_rate, 2) if 'error_rate' in locals() else 0,
                "total_critical_errors": comprehensive_stats.get("entries_by_type", {}).get("critical", 0) if comprehensive_stats else 0,
                "unique_error_categories": len(comprehensive_stats.get("error_categories", {})) if comprehensive_stats else 0,
                "diagnostic_insights": comprehensive_stats.get("diagnostic_insights", []) if comprehensive_stats else []
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.datetime.now().isoformat(),
            "total_logs": len(scraper_logs) if scraper_logs else 0
        }

@app.get("/api/scraper-logs/session/{session_id}", tags=["scraper"])
async def get_session_logs(session_id: str):
    """Get logs for a specific session."""
    try:
        session_logs = [log for log in scraper_logs if log.get("session_id") == session_id]
        
        return {
            "session_id": session_id,
            "logs": session_logs,
            "count": len(session_logs),
            "timestamp": datetime.datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "error": str(e),
            "session_id": session_id,
            "timestamp": datetime.datetime.now().isoformat()
        }

@app.get("/api/scraper-logs/error-analysis", tags=["scraper"])
async def get_error_analysis(
    hours_back: Optional[int] = 24,
    session_id: Optional[str] = None
):
    """Erweiterte Fehleranalyse mit Diagnoseempfehlungen."""
    try:
        # Filter für Zeitraum
        cutoff_time = datetime.datetime.now() - datetime.timedelta(hours=hours_back)
        
        filtered_logs = scraper_logs
        if session_id:
            filtered_logs = [log for log in filtered_logs if log.get("session_id") == session_id]
        
        # Nur Logs aus dem gewünschten Zeitraum
        recent_logs = []
        for log in filtered_logs:
            try:
                log_time = datetime.datetime.fromisoformat(log.get("timestamp", "").replace('Z', '+00:00'))
                if log_time.replace(tzinfo=None) >= cutoff_time:
                    recent_logs.append(log)
            except Exception:
                pass  # Skip logs with invalid timestamps
        
        # Fehleranalyse durchführen
        error_analysis = {
            "analysis_period": f"Last {hours_back} hours",
            "total_logs_analyzed": len(recent_logs),
            "error_summary": {
                "total_errors": 0,
                "critical_errors": 0,
                "browser_errors": 0,
                "network_errors": 0,
                "memory_errors": 0,
                "filesystem_errors": 0,
                "parsing_errors": 0
            },
            "error_patterns": {},
            "performance_issues": [],
            "diagnostic_recommendations": [],
            "error_timeline": [],
            "top_error_messages": {},
            "session_error_breakdown": {}
        }
        
        error_messages = {}
        session_errors = {}
        
        for log in recent_logs:
            if log.get("event_type") in ["error", "critical"]:
                error_analysis["error_summary"]["total_errors"] += 1
                
                if log.get("event_type") == "critical":
                    error_analysis["error_summary"]["critical_errors"] += 1
                
                # Kategorisiere Fehler
                error_category = log.get("data", {}).get("error_category", "unknown")
                if error_category in ["browser", "network", "memory", "filesystem", "parsing"]:
                    error_analysis["error_summary"][f"{error_category}_errors"] += 1
                
                # Sammle Fehlermuster
                if error_category not in error_analysis["error_patterns"]:
                    error_analysis["error_patterns"][error_category] = {
                        "count": 0,
                        "common_causes": log.get("data", {}).get("error_analysis", {}).get("common_causes", []),
                        "suggested_actions": log.get("data", {}).get("error_analysis", {}).get("suggested_actions", []),
                        "diagnostic_tips": log.get("data", {}).get("diagnostic_tips", [])
                    }
                error_analysis["error_patterns"][error_category]["count"] += 1
                
                # Timeline für Fehler
                error_analysis["error_timeline"].append({
                    "timestamp": log.get("timestamp"),
                    "category": error_category,
                    "message": log.get("message", "")[:100],  # Begrenzt auf 100 Zeichen
                    "severity": log.get("event_type")
                })
                
                # Häufige Fehlermeldungen
                message = log.get("message", "Unknown error")
                if message in error_messages:
                    error_messages[message] += 1
                else:
                    error_messages[message] = 1
                
                # Session-basierte Fehlerverteilung
                session = log.get("session_id", "no_session")
                if session not in session_errors:
                    session_errors[session] = 0
                session_errors[session] += 1
            
            # Performance-Probleme erkennen
            perf_info = log.get("data", {}).get("performance_info", {})
            if isinstance(perf_info, dict):
                memory_mb = perf_info.get("memory_rss_mb", 0)
                cpu_percent = perf_info.get("cpu_percent", 0)
                
                if memory_mb > 800:  # Hoher Speicherverbrauch
                    error_analysis["performance_issues"].append({
                        "type": "high_memory",
                        "value": memory_mb,
                        "timestamp": log.get("timestamp"),
                        "message": f"Hoher Speicherverbrauch: {memory_mb} MB"
                    })
                
                if cpu_percent > 90:  # Hohe CPU-Last
                    error_analysis["performance_issues"].append({
                        "type": "high_cpu",
                        "value": cpu_percent,
                        "timestamp": log.get("timestamp"),
                        "message": f"Hohe CPU-Last: {cpu_percent}%"
                    })
        
        # Top Fehlermeldungen (maximal 10)
        error_analysis["top_error_messages"] = dict(
            sorted(error_messages.items(), key=lambda x: x[1], reverse=True)[:10]
        )
        
        # Session Error Breakdown
        error_analysis["session_error_breakdown"] = session_errors
        
        # Sortiere Timeline nach Zeit (neueste zuerst)
        error_analysis["error_timeline"] = sorted(
            error_analysis["error_timeline"], 
            key=lambda x: x["timestamp"], 
            reverse=True
        )[:20]  # Nur die letzten 20 Fehler
        
        # Diagnostische Empfehlungen basierend auf Fehlern generieren
        recommendations = []
        
        if error_analysis["error_summary"]["browser_errors"] > 5:
            recommendations.append({
                "priority": "high",
                "category": "browser",
                "recommendation": "Häufige Browser-Fehler erkannt. Browser-Installation und Netzwerkverbindung prüfen.",
                "actions": ["Browser neu installieren", "Netzwerk-Diagnose", "Headless-Modus testen"]
            })
        
        if error_analysis["error_summary"]["memory_errors"] > 2:
            recommendations.append({
                "priority": "critical",
                "category": "memory",
                "recommendation": "Speicherprobleme erkannt. Server-Ressourcen erhöhen oder Memory-Leaks prüfen.",
                "actions": ["RAM erhöhen", "Memory-Profiling", "Browser-Instanzen begrenzen"]
            })
        
        if len(error_analysis["performance_issues"]) > 10:
            recommendations.append({
                "priority": "medium",
                "category": "performance",
                "recommendation": "Performance-Probleme erkannt. System-Optimierung empfohlen.",
                "actions": ["CPU/Memory Monitoring", "System-Tuning", "Load-Balancing"]
            })
        
        if error_analysis["error_summary"]["network_errors"] > 3:
            recommendations.append({
                "priority": "high",
                "category": "network",
                "recommendation": "Netzwerk-Probleme erkannt. Verbindungsqualität und DNS prüfen.",
                "actions": ["Netzwerk-Diagnose", "DNS-Check", "Rate-Limiting prüfen"]
            })
        
        error_analysis["diagnostic_recommendations"] = recommendations
        
        return {
            "status": "success",
            "timestamp": datetime.datetime.now().isoformat(),
            "analysis": error_analysis
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.datetime.now().isoformat()
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
    
    # Log the startup process
    print("\n[STARTUP] ======================================")
    print("[STARTUP] GULP Scraper API wird gestartet...")
    print(f"[STARTUP] Cloud Environment: {IS_CLOUD_ENV}")
    print(f"[STARTUP] Use Real Scraper: {USE_REAL_SCRAPER}")
    print(f"[STARTUP] Data Directory: {DATA_DIR.absolute()}")
    print("[STARTUP] ======================================\n")
    
    # Lade gespeicherte Scraper-Logs
    load_logs_from_file()
    
    # Log the startup event
    log_scraper_event("info", "API Startup initiated", {
        "is_cloud_env": IS_CLOUD_ENV,
        "use_real_scraper": USE_REAL_SCRAPER,
        "data_dir": str(DATA_DIR.absolute())
    })
    
    # Initialisiere den Projekt-Manager
    project_manager = ProjectManager(DATA_DIR)
    log_scraper_event("info", "ProjectManager initialized", {"data_dir": str(DATA_DIR)})
    
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
    log_scraper_event("info", "Scheduler configuration completed", scheduler_config)
    
    # Make sure the scheduler is not already running before starting it
    if not scheduler.running:
        try:
            scheduler.start()
            print("Scheduler started successfully")
            log_scraper_event("success", "Scheduler started successfully", {"running": scheduler.running})
        except Exception as e:
            print(f"Error starting scheduler: {str(e)}")
            log_scraper_event("error", f"Error starting scheduler: {str(e)}")
    
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
                log_scraper_event("info", "Email service configured for Render", new_config)
        
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
                        # Use a more compatible approach for timezone handling
                        try:
                            last_scrape_time = datetime.datetime.now().replace(microsecond=0).isoformat() + 'Z'  # UTC format
                        except Exception as e:
                            print(f"Error formatting last_scrape_time: {str(e)}")
                            last_scrape_time = datetime.datetime.now().isoformat()  # Fallback
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
    
    # Final startup completion log
    print("\n[STARTUP] ======================================")
    print("[STARTUP] API Startup completed successfully!")
    print("[STARTUP] ======================================\n")
    log_scraper_event("success", "API Startup completed successfully", {
        "scheduler_running": scheduler.running,
        "email_configured": email_service.is_configured if email_service else False,
        "project_manager_ready": project_manager is not None
    })
    
    # Force flush all output to ensure logs are visible immediately
    sys.stdout.flush()
    sys.stderr.flush()


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
    global email_notification_enabled, last_scrape_time, current_scrape_session
    
    if is_scraping:
        return JSONResponse(
            status_code=409,
            content={"error": "A scrape is already in progress"}
        )
    
    # Erstelle eine neue Session-ID für diese Scrape-Session
    current_scrape_session = f"manual-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    
    print(f"\n[MANUAL SCRAPE] Manueller Scrape-Vorgang gestartet (Session: {current_scrape_session})")
    print(f"[MANUAL SCRAPE] Umgebung: {'Render/Cloud' if IS_CLOUD_ENV else 'Lokal'}")
    print(f"[MANUAL SCRAPE] USE_REAL_SCRAPER={USE_REAL_SCRAPER}")
    
    # Log den Startvorgang mit Session-ID
    start_log = log_scraper_event("info", "Manueller Scrape gestartet", {
        "is_cloud_env": IS_CLOUD_ENV,
        "use_real_scraper": USE_REAL_SCRAPER,
        "pages": str(pages) if 'pages' in locals() else str(PAGE_RANGE),
        "session_id": current_scrape_session,
        "trigger_type": "manual",
        "send_email": request.send_email
    }, session_id=current_scrape_session)
    
    # Stelle sicher, dass die Logs auch in der Konsole sichtbar sind
    sys.stdout.flush()
        
    # Convert the pages list to a range if provided
    if request.pages:
        pages = list(range(min(request.pages), max(request.pages) + 1))
    else:
        pages = list(PAGE_RANGE)
    
    # Aktiviere E-Mail-Benachrichtigung für diesen Scrape-Vorgang, wenn angefordert
    if request.send_email:
        email_notification_enabled = True
    else:
        email_notification_enabled = False
    
    # Direkter Scrape statt Hintergrundaufgabe, um sofortige Rückmeldung zu ermöglichen
    try:
        # Starte den Scrape-Vorgang direkt
        print(f"[MANUAL SCRAPE] Führe Scrape direkt aus...")
        
        # If real scraper is disabled, return empty result with warning
        if not USE_REAL_SCRAPER:
            warning_msg = "Real scraper is disabled (USE_REAL_SCRAPER=False)"
            print(f"[MANUAL SCRAPE] {warning_msg}")
            log_scraper_event("warning", warning_msg, {
                "use_real_scraper": USE_REAL_SCRAPER,
                "session_id": current_scrape_session
            }, session_id=current_scrape_session)
            
            # Session beenden
            current_scrape_session = None
            
            return {
                "message": "Scraper ist deaktiviert - keine Daten verfügbar",
                "success": False,
                "project_count": 0,
                "new_project_count": 0,
                "warning": warning_msg,
                "session_id": None
            }
        
        # Normaler Scrape-Vorgang (nicht Render oder explizit USE_REAL_SCRAPER=True)
        print(f"[MANUAL SCRAPE] Starte echten Scraper mit USE_REAL_SCRAPER={USE_REAL_SCRAPER}")
        log_scraper_event("info", "Starte echten Scraper", {
            "is_cloud_env": IS_CLOUD_ENV,
            "use_real_scraper": USE_REAL_SCRAPER,
            "pages": str(pages),
            "session_id": current_scrape_session
        }, session_id=current_scrape_session)
        
        try:
            # scrape_gulp ist NICHT async, also nicht mit await aufrufen
            projects = scrape_gulp(pages)
            print(f"[MANUAL SCRAPE] Scraper abgeschlossen, {len(projects)} Projekte gefunden")
            log_scraper_event("success", "Echter Scraper abgeschlossen", {
                "projects_count": len(projects),
                "session_id": current_scrape_session
            }, session_id=current_scrape_session)
        except Exception as e:
            import traceback  # Import hier hinzufügen
            error_msg = f"Fehler beim Ausführen des Scrapers: {str(e)}"
            print(f"[MANUAL SCRAPE ERROR] {error_msg}")
            print(f"[MANUAL SCRAPE ERROR] Full traceback: {traceback.format_exc()}")
            log_scraper_event("error", error_msg, {
                "traceback": traceback.format_exc(),
                "session_id": current_scrape_session
            }, session_id=current_scrape_session)
            # Stelle sicher, dass Fehler-Logs auch in der Konsole sichtbar sind
            sys.stderr.flush()
            # Session beenden bei Fehler
            current_scrape_session = None
            return JSONResponse(
                status_code=500,
                content={"error": error_msg}
            )
        
        # Stelle sicher, dass der letzte Scrape-Zeitpunkt aktualisiert wird
        # Use a more compatible approach for timezone handling
        try:
            last_scrape_time = datetime.datetime.now().replace(microsecond=0).isoformat() + 'Z'  # UTC format
        except Exception as e:
            print(f"Error formatting last_scrape_time: {str(e)}")
            last_scrape_time = datetime.datetime.now().isoformat()  # Fallback
        log_scraper_event("info", "Letzter Scrape-Zeitpunkt aktualisiert", {
            "timestamp": last_scrape_time,
            "session_id": current_scrape_session
        }, session_id=current_scrape_session)
        
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
        
        # Abschließendes Erfolgs-Log
        log_scraper_event("success", "Manueller Scrape erfolgreich abgeschlossen", {
            "project_count": project_count,
            "new_project_count": new_project_count,
            "last_scrape_time": last_scrape_time,
            "session_id": current_scrape_session,
            "email_notification": email_notification_enabled and email_recipient != ""
        }, session_id=current_scrape_session)
        
        # Session beenden
        completed_session = current_scrape_session
        current_scrape_session = None
        
        return {
            "message": "Scrape wurde erfolgreich durchgeführt",
            "success": True,
            "last_scrape": last_scrape_time,
            "project_count": project_count,
            "new_project_count": new_project_count,
            "email_notification": email_notification_enabled and email_recipient != "",
            "session_id": completed_session
        }
    except Exception as e:
        print(f"[MANUAL SCRAPE] Fehler beim Scrapen: {str(e)}")
        import traceback
        print(f"[MANUAL SCRAPE] Traceback: {traceback.format_exc()}")
        log_scraper_event("error", f"Kritischer Fehler beim Scrapen: {str(e)}", {
            "traceback": traceback.format_exc(),
            "session_id": current_scrape_session,
            "error_type": "critical_scrape_error"
        }, session_id=current_scrape_session)
        # Stelle sicher, dass Fehler-Logs auch in der Konsole sichtbar sind
        sys.stderr.flush()
        # Session bei kritischem Fehler beenden
        current_scrape_session = None
        return JSONResponse(
            status_code=500,
            content={
                "error": f"Fehler beim Scrapen: {str(e)}",
                "success": False
            }
        )

# Alias for /trigger-scrape endpoint for backward compatibility
@app.post("/trigger-scrape")
async def trigger_scrape_alias(
    background_tasks: BackgroundTasks,
    request: ScrapeRequest = ScrapeRequest()
):
    """Alias for the main scrape endpoint for backward compatibility."""
    return await trigger_scrape(background_tasks, request)

# Main Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Run the API server
    uvicorn.run("scraper:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8001)), log_level="info")
