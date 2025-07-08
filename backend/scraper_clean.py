#!/usr/bin/env python3
"""
Clean GULP Scraper - working version with new API
"""

import asyncio
import json
import re
import datetime
import uuid
import time
import traceback
import sys
from typing import List, Dict
from playwright.async_api import async_playwright

# Configuration
USE_REAL_SCRAPER = True  # Set to False for testing with dummy data
API_RE = re.compile(r'/rest/internal/projects/search')
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/137.0.0.0 Safari/537.36"
)

# Standalone logging function
def log_scraper_event(level, message, data=None, correlation_id=None, tags=None):
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] [{level.upper()}] {message}")
    if data:
        print(f"  Data: {data}")
    if correlation_id:
        print(f"  Correlation ID: {correlation_id}")
    if tags:
        print(f"  Tags: {', '.join(tags)}")
    sys.stdout.flush()

# Global state
is_scraping = False
last_scrape_time = None

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
                
            except Exception as e:
                log_scraper_event(
                    "warning",
                    "Page load timeout/error - continuing with API capture",
                    {"error": str(e)},
                    correlation_id=correlation_id,
                    tags=["page_load", "timeout", "warning"]
                )
                await asyncio.sleep(3)
            
        except Exception as e:
            log_scraper_event(
                "error",
                "Error in scraper process",
                {"error": str(e)},
                correlation_id=correlation_id,
                tags=["scraper", "error"]
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

async def scrape_gulp_clean(pages=None):
    """Clean scraper function with the new GULP API"""
    global is_scraping, last_scrape_time
    
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
    
    try:
        log_scraper_event(
            "info", 
            f"Starting GULP scraper", 
            {
                "timestamp": datetime.datetime.now().astimezone().isoformat(),
                "use_real_scraper": USE_REAL_SCRAPER,
                "correlation_id": correlation_id
            },
            correlation_id=correlation_id,
            tags=["scraper_start", "gulp"]
        )
        
        # Use dummy data for local testing or real scraper for production
        if not USE_REAL_SCRAPER:
            # Use dummy data
            dummy_projects = [
                {
                    "id": "dummy-1",
                    "title": "Sample Project 1",
                    "description": "Test project for development",
                    "location": "Remote",
                    "companyName": "Test Company",
                    "datePosted": datetime.datetime.now().isoformat(),
                    "type": "GULP_PROJECT"
                },
                {
                    "id": "dummy-2",
                    "title": "Sample Project 2",
                    "description": "Another test project",
                    "location": "Berlin",
                    "companyName": "Another Company",
                    "datePosted": datetime.datetime.now().isoformat(),
                    "type": "TALENT_FINDER"
                }
            ]
            all_projects = dummy_projects
            log_scraper_event(
                "info",
                "Using dummy data for testing",
                {"projects_count": len(dummy_projects)},
                correlation_id=correlation_id,
                tags=["dummy_data", "testing"]
            )
        else:
            # Use real scraper with new GULP API
            all_projects = await scrape_gulp_real(correlation_id)
        
        # Set the last scrape time
        last_scrape_time = datetime.datetime.now().astimezone()
        
        log_scraper_event(
            "info", 
            "GULP scraper completed successfully", 
            {
                "projects_found": len(all_projects),
                "timestamp": last_scrape_time.isoformat(),
                "correlation_id": correlation_id
            },
            correlation_id=correlation_id,
            tags=["scraper_success", "completed"]
        )
        
        return all_projects
        
    except Exception as main_scraper_error:
        # Main error handling for the entire scraper process
        log_scraper_event(
            "error", 
            "Critical error in main scraper process", 
            {
                "error": str(main_scraper_error),
                "error_type": type(main_scraper_error).__name__,
                "traceback": traceback.format_exc(),
                "correlation_id": correlation_id,
                "use_real_scraper": USE_REAL_SCRAPER
            },
            correlation_id=correlation_id,
            tags=["scraper_error", "critical_error", "main_process_error"]
        )
        print(f"Critical scraper error: {main_scraper_error}")
        print(f"Full traceback: {traceback.format_exc()}")
        sys.stdout.flush()
        sys.stderr.flush()
        
    finally:
        # Reset the scraping flag in any case
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
            "use_real_scraper": USE_REAL_SCRAPER,
            "reason": "No projects found or scraping process failed"
        },
        correlation_id=correlation_id,
        tags=["scraper_error", "empty_result", "no_data"]
    )
    return []

if __name__ == "__main__":
    async def test_scraper():
        print(f'USE_REAL_SCRAPER: {USE_REAL_SCRAPER}')
        projects = await scrape_gulp_clean()
        print(f'Scraper returned {len(projects)} projects')
        if projects:
            print(f'First project: {projects[0].get("title", "No title")}')
            print(f'First project keys: {list(projects[0].keys())[:10]}')
        return projects

    result = asyncio.run(test_scraper())
