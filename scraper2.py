"""
GULP Job Scraper API - Cloud Version (Cleaned)
==============================================
Bereinigte Version des originalen gulp22.py Skripts für Cloud-APIs.
"""

import asyncio
import json
import os
import re
import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any

import uvicorn
from fastapi import FastAPI, BackgroundTasks, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from project_manager import ProjectManager
from email_service import EmailService
from email_test_route import router as email_router

# Playwright Import
try:
    from playwright.async_api import async_playwright, TimeoutError as PwTimeout
except ImportError:
    raise ImportError(
        "Playwright not installed. Run: pip install playwright && playwright install chromium"
    )

# -----------------------------------------------------------
# Environment Flags
# -----------------------------------------------------------

IS_CLOUD_ENV = os.environ.get('RENDER', False) or os.environ.get('CLOUD_ENV', False)
USE_REAL_SCRAPER = os.environ.get('USE_REAL_SCRAPER', 'True').lower() in ('true', '1', 't')

if IS_CLOUD_ENV and 'USE_REAL_SCRAPER' not in os.environ:
    print("[RENDER CONFIG] Defaulting USE_REAL_SCRAPER=False")
    USE_REAL_SCRAPER = False

# -----------------------------------------------------------
# FastAPI & CORS
# -----------------------------------------------------------

app = FastAPI(
    title="GULP Job Scraper API",
    description="API for scraping and accessing GULP job listings",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:8000",
        "https://*.onrender.com",
        "https://*.render.com",
        os.environ.get("FRONTEND_URL", "*")
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(email_router, prefix="/api/email", tags=["email"])

# -----------------------------------------------------------
# Global Config
# -----------------------------------------------------------

START_URL_TEMPLATE = "https://www.gulp.de/gulp2/g/projekte?page={page}"
PAGE_RANGE = range(1, 4)
HEADLESS = True if IS_CLOUD_ENV else os.environ.get('HEADLESS', 'True').lower() in ('true', '1', 't')
TIMEOUT_MS = 45_000

launch_options = {
    "headless": HEADLESS,
    "args": ["--no-sandbox", "--disable-dev-shm-usage"],
    "timeout": TIMEOUT_MS
}

DATA_DIR = Path(os.environ.get('DATA_DIR', 'data'))
DATA_DIR.mkdir(exist_ok=True)
OUTPUT_JSON = DATA_DIR / "gulp_projekte_raw.json"
DEBUG_DIR = DATA_DIR / "debug"
DEBUG_DIR.mkdir(exist_ok=True)
LAST_SCRAPE_FILE = DATA_DIR / "last_scrape.txt"

print(f"Using data dir: {DATA_DIR.absolute()}")

# Email Config
DEFAULT_EMAIL_RECIPIENT = os.environ.get("EMAIL_RECIPIENT", "m.banner@realcore.de")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost")
DEFAULT_SMTP_HOST = os.environ.get("SMTP_HOST", "mail.tk-core.de")
DEFAULT_SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))
DEFAULT_SMTP_USER = os.environ.get("SMTP_USER", "gulpai@tk-core.de")
DEFAULT_SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "gulpai2025")
DEFAULT_EMAIL_SENDER = os.environ.get("EMAIL_SENDER", "GULP Job Scraper <gulpai@tk-core.de>")

API_RE = re.compile(r"/rest/internal/projects/search", re.I)
PROJ_KEY_CANDIDATES = {"title", "jobTitle"}

# -----------------------------------------------------------
# Globals
# -----------------------------------------------------------

email_service = None
project_manager = None
scheduler = AsyncIOScheduler()
scheduler_config = {
    "enabled": True,
    "interval_days": 1,
    "daily_runs": [{"hour": i, "minute": 0} for i in range(0, 24)]
}

is_scraping = False
last_scrape_time = None
email_notification_enabled = True
email_recipient = DEFAULT_EMAIL_RECIPIENT
last_used_dummy_data = False

# -----------------------------------------------------------
# Helper: Dummy Projects
# -----------------------------------------------------------

def create_dummy_projects(n: int = 10) -> List[Dict]:
    now = datetime.datetime.utcnow()
    return [
        {
            "id": f"dummy-{i+1}",
            "title": f"Dummy-Projekt {i+1}",
            "description": "Auto-generated dummy project",
            "companyName": "Demo GmbH",
            "location": "Remote",
            "isRemoteWorkPossible": True,
            "publicationDate": now.strftime("%d.%m.%Y"),
            "originalPublicationDate": now.isoformat(),
            "url": "https://www.gulp.de/"
        }
        for i in range(n)
    ]

# -----------------------------------------------------------
# Scraper Logic (minimal)
# -----------------------------------------------------------

async def scrape_gulp(pages: range = PAGE_RANGE) -> List[Dict]:
    global is_scraping, last_scrape_time, last_used_dummy_data
    if is_scraping:
        print("Scrape in progress...")
        return []

    is_scraping = True
    all_projects = []

    try:
        if not USE_REAL_SCRAPER:
            print("USE_REAL_SCRAPER=False → Using dummy data.")
            dummy = create_dummy_projects()
            unique, _ = project_manager.process_projects(dummy)
            last_used_dummy_data = True
            last_scrape_time = datetime.datetime.now().isoformat()
            return unique

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(**launch_options)
            context = await browser.new_context()
            page = await context.new_page()

            for page_idx in pages:
                await page.goto(START_URL_TEMPLATE.format(page=page_idx))
                await asyncio.sleep(1)

            await page.close()
            await context.close()
            await browser.close()

        last_scrape_time = datetime.datetime.now().isoformat()
        last_used_dummy_data = False
        return []

    finally:
        is_scraping = False

# -----------------------------------------------------------
# API Models
# -----------------------------------------------------------

class ScrapeRequest(BaseModel):
    pages: Optional[List[int]] = None
    send_email: bool = False

class EmailConfig(BaseModel):
    smtp_host: str
    smtp_port: int = 587
    smtp_user: str
    smtp_password: str
    sender: Optional[str] = None
    recipient: EmailStr
    enabled: bool = True
    frontend_url: Optional[str] = None

# -----------------------------------------------------------
# API Endpoints (minimal)
# -----------------------------------------------------------

@app.post("/scrape")
async def trigger_scrape(request: ScrapeRequest):
    pages = PAGE_RANGE
    if request.pages:
        pages = range(min(request.pages), max(request.pages) + 1)
    await scrape_gulp(pages)
    return {"message": "Scrape triggered"}

@app.get("/status")
async def get_status():
    return {
        "is_scraping": is_scraping,
        "last_scrape": last_scrape_time,
        "dummy_data": last_used_dummy_data
    }

# -----------------------------------------------------------
# Startup
# -----------------------------------------------------------

@app.on_event("startup")
async def startup_event():
    global project_manager, email_service
    project_manager = ProjectManager(DATA_DIR)
    email_service = EmailService(
        smtp_host=DEFAULT_SMTP_HOST,
        smtp_port=DEFAULT_SMTP_PORT,
        smtp_user=DEFAULT_SMTP_USER,
        smtp_password=DEFAULT_SMTP_PASSWORD,
        sender=DEFAULT_EMAIL_SENDER,
        frontend_url=FRONTEND_URL
    )
    scheduler.start()

# -----------------------------------------------------------
# Main Entry
# -----------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run("gulp_scraper_api:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8001)), log_level="info")

