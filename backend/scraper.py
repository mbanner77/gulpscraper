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

API_RE = re.compile(r"/rest/internal/projects/search", re.I)
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


async def scrape_gulp(pages: range = PAGE_RANGE):
    """Run the GULP scraper and return the projects."""
    global is_scraping, last_scrape_time, project_manager, email_service, email_notification_enabled, email_recipient
    
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
                "timestamp": datetime.datetime.now().astimezone().isoformat(),
                "use_real_scraper": USE_REAL_SCRAPER,
                "is_cloud_env": IS_CLOUD_ENV,
                "pages": list(pages),
                "correlation_id": correlation_id
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
            "data_dir": str(DATA_DIR.absolute()),
            "correlation_id": correlation_id
        }, correlation_id=correlation_id, tags=["render", "environment"])
        print(f"[RENDER DEBUG] Ausgabedatei existiert: {OUTPUT_JSON.exists()}")
        print(f"[RENDER DEBUG] USE_REAL_SCRAPER={USE_REAL_SCRAPER}")
        if OUTPUT_JSON.exists():
            try:
                with open(OUTPUT_JSON, 'r', encoding='utf-8') as f:
                    project_count = len(json.load(f))
                    print(f"[RENDER DEBUG] Anzahl Projekte in Datei: {project_count}")
                    log_scraper_event("info", "Existing project data found", {
                        "project_count": project_count,
                        "correlation_id": correlation_id
                    }, correlation_id=correlation_id, tags=["render", "existing_data"])
            except Exception as e:
                print(f"[RENDER DEBUG] Fehler beim Lesen der Projektdatei: {str(e)}")
                log_scraper_event("error", "Error reading existing project data", {
                    "error": str(e),
                    "correlation_id": correlation_id
                }, correlation_id=correlation_id, tags=["render", "data_error"])
    
    # If USE_REAL_SCRAPER is False, skip scraping and return empty result
    if not USE_REAL_SCRAPER:
        log_scraper_event(
            "warning", 
            "USE_REAL_SCRAPER is disabled, skipping scrape",
            {"correlation_id": correlation_id},
            correlation_id=correlation_id,
            tags=["scraper_disabled"]
        )
        is_scraping = False
        return []
    
    # Ab hier beginnt der echte Scraper mit Playwright
    try:
        log_scraper_event(
            "info", 
            "Initializing browser configuration", 
            {
                "headless": HEADLESS,
                "timeout_ms": TIMEOUT_MS,
                "is_cloud_env": IS_CLOUD_ENV,
                "correlation_id": correlation_id
            },
            correlation_id=correlation_id,
            tags=["browser", "configuration"]
        )
        
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
                                except Exception as nav_log_error:
                                    log_scraper_event(
                                        "error", 
                                        "Error logging navigation start", 
                                        {"error": str(nav_log_error)},
                                        correlation_id=correlation_id,
                                        tags=["error", "logging_error", "navigation"]
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
                                
                                # Scroll through the page to trigger lazy loading
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
                                
                                # Handle any other navigation errors
                                try:
                                    # This is a placeholder try block to maintain the structure
                                    pass
                                except Exception as main_navigation_error:
                                    log_scraper_event(
                                        "error", 
                                        "Unhandled error during page navigation and processing", 
                                        {
                                            "error": str(main_navigation_error),
                                            "traceback": traceback.format_exc()
                                        },
                                        correlation_id=correlation_id,
                                        tags=["error", "navigation", "critical"]
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
                                    # Use a more compatible approach for timezone handling
                                    try:
                                        last_scrape_time = datetime.datetime.now().replace(microsecond=0).isoformat() + 'Z'  # UTC format
                                    except Exception as e:
                                        print(f"Error formatting last_scrape_time: {str(e)}")
                                        last_scrape_time = datetime.datetime.now().isoformat()  # Fallback
                                    
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
                "traceback": traceback.format_exc(),
                "correlation_id": correlation_id
            }, correlation_id=correlation_id, tags=["playwright", "initialization_error"])
            
    except Exception as main_scraper_error:
        # Hauptfehlerbehandlung für den gesamten Scraper-Prozess
        log_scraper_event(
            "error", 
            "Critical error in main scraper process", 
            {
                "error": str(main_scraper_error),
                "error_type": type(main_scraper_error).__name__,
                "traceback": traceback.format_exc(),
                "correlation_id": correlation_id,
                "pages_attempted": list(pages),
                "use_real_scraper": USE_REAL_SCRAPER,
                "is_cloud_env": IS_CLOUD_ENV
            },
            correlation_id=correlation_id,
            tags=["scraper_error", "critical_error", "main_process"]
        )
        print(f"[SCRAPER ERROR] Critical error: {str(main_scraper_error)}")
        print(f"[SCRAPER ERROR] Traceback: {traceback.format_exc()}")
        sys.stderr.flush()
        
    finally:
        # Reset the scraping flag in jedem Fall
        is_scraping = False
        log_scraper_event(
            "info", 
            "Scraper process completed, resetting flags", 
            {
                "correlation_id": correlation_id,
                "is_scraping_reset": True
            },
            correlation_id=correlation_id,
            tags=["scraper_cleanup", "process_completed"]
        )
    
    # If we reach here, scraping failed
    log_scraper_event(
        "error", 
        "Scraping completed but no results returned", 
        {
            "correlation_id": correlation_id,
            "pages_attempted": list(pages),
            "use_real_scraper": USE_REAL_SCRAPER,
            "is_cloud_env": IS_CLOUD_ENV,
            "reason": "No projects found or scraping process failed"
        },
        correlation_id=correlation_id,
        tags=["scraper_error", "empty_result", "no_data"]
    )
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
        # Event Type Statistiken
        event_type = log.get("event_type", "unknown")
        stats["entries_by_type"][event_type] = stats["entries_by_type"].get(event_type, 0) + 1
        
        # Log Level Statistiken  
        log_level = log.get("log_level", "INFO")
        stats["entries_by_level"][log_level] = stats["entries_by_level"].get(log_level, 0) + 1
        
        # Error Category Analyse
        if log.get("data", {}).get("error_category"):
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
        log_file_exists = SCRAPER_LOGS_FILE.exists() if SCRAPER_LOGS_FILE else False
        log_file_size = SCRAPER_LOGS_FILE.stat().st_size if log_file_exists else 0
        
        # Calculate recent activity
        now = datetime.datetime.now()
        recent_logs = []
        if scraper_logs:
            for log in scraper_logs[-10:]:  # Last 10 logs
                try:
                    log_time = datetime.datetime.fromisoformat(log.get("timestamp", "").replace('Z', '+00:00'))
                    time_diff = (now - log_time).total_seconds()
                    if time_diff < 300:  # Last 5 minutes
                        recent_logs.append({
                            "timestamp": log.get("timestamp"),
                            "event_type": log.get("event_type"),
                            "message": log.get("message")
                        })
                except Exception:
                    pass  # Skip logs with invalid timestamps
        
        # Generiere umfassende Statistiken
        comprehensive_stats = aggregate_log_statistics()
        
        # Unique Sessions für bessere Übersicht
        unique_sessions = list(set(log.get("session_id") for log in scraper_logs if log.get("session_id")))
        
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
        
        return {
            "status": "ok",
            "timestamp": datetime.datetime.now().isoformat(),
            "log_file": {
                "exists": log_file_exists,
                "size_bytes": log_file_size,
                "path": str(SCRAPER_LOGS_FILE) if SCRAPER_LOGS_FILE else None,
                "total_logs": len(scraper_logs),
                "memory_logs_count": len(scraper_logs),
            },
            "recent_activity": recent_logs,
            "environment": {
                "is_cloud": IS_CLOUD_ENV,
                "use_real_scraper": USE_REAL_SCRAPER,
                "headless": HEADLESS,
                "last_log_timestamp": scraper_logs[-1].get("timestamp") if scraper_logs else None,
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
                "session_logs_count": len([log for log in scraper_logs if log.get("session_id") == current_scrape_session]) if current_scrape_session else 0
            },
            "comprehensive_statistics": comprehensive_stats,
            "session_overview": {
                "total_sessions": len(unique_sessions),
                "active_session": current_scrape_session,
                "recent_sessions": unique_sessions[-5:] if len(unique_sessions) > 5 else unique_sessions
            },
            "health_indicators": health_indicators,
            "system_metrics": {
                "error_rate_percent": round(error_rate, 2),
                "total_critical_errors": comprehensive_stats.get("entries_by_type", {}).get("critical", 0),
                "unique_error_categories": len(comprehensive_stats.get("error_categories", {})),
                "diagnostic_insights": comprehensive_stats.get("diagnostic_insights", [])
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
            projects = await scrape_gulp(pages)
            print(f"[MANUAL SCRAPE] Scraper abgeschlossen, {len(projects)} Projekte gefunden")
            log_scraper_event("success", "Echter Scraper abgeschlossen", {
                "projects_count": len(projects),
                "session_id": current_scrape_session
            }, session_id=current_scrape_session)
        except Exception as e:
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

# Main Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Run the API server
    uvicorn.run("scraper:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8001)), log_level="info")
