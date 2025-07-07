#!/usr/bin/env python3
"""
Minimal funktionierender GULP Scraper - zu verwenden als Ersatz für die defekte scrape_gulp Funktion
"""

import asyncio
import json
import re
import datetime
import uuid
import time
from playwright.async_api import async_playwright

# Neue API-Pattern für GULP
API_RE = re.compile(r'/rest/internal/projects/search')

async def scrape_gulp_fixed(correlation_id=None):
    """
    Funktionierender GULP Scraper mit der neuen API-Struktur
    """
    if not correlation_id:
        correlation_id = f"scrape-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    
    print(f"[{correlation_id}] Starting GULP scraper with new API...")
    
    captured_projects = []
    
    async def process_api_response(response):
        """Process the new GULP API response format"""
        if response and API_RE.search(response.url) and response.status == 200:
            try:
                data = await response.json()
                print(f"[{correlation_id}] API Response received: {response.url}")
                print(f"[{correlation_id}] Response keys: {data.keys()}")
                
                # Neue API-Struktur: {'totalCount': int, 'projects': [...]}
                if 'projects' in data:
                    projects = data['projects']
                    print(f"[{correlation_id}] Found {len(projects)} projects")
                    captured_projects.extend(projects)
                    
                    # Zeige einige Beispiele
                    for i, project in enumerate(projects[:3]):
                        print(f"[{correlation_id}] Project {i+1}: {project.get('title', 'No title')[:50]}...")
                
                return data
            except Exception as e:
                print(f"[{correlation_id}] Error processing API response: {e}")
        return None
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        # Handle API responses
        page.on("response", process_api_response)
        
        try:
            print(f"[{correlation_id}] Loading GULP project page...")
            
            # Versuche die Seite zu laden (mit Timeout-Behandlung)
            try:
                await page.goto("https://www.gulp.de/gulp2/g/projekte", timeout=15000, wait_until="domcontentloaded")
                print(f"[{correlation_id}] Page loaded successfully")
                
                # Warte auf API-Calls
                await asyncio.sleep(5)
                
                # Versuche zu scrollen, um mehr Projekte zu laden
                try:
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await asyncio.sleep(2)
                    print(f"[{correlation_id}] Scrolled page to load more projects")
                except Exception as e:
                    print(f"[{correlation_id}] Scroll error (not critical): {e}")
                
            except Exception as e:
                print(f"[{correlation_id}] Page load timeout/error: {e}")
                print(f"[{correlation_id}] Continuing - API calls might still work...")
                await asyncio.sleep(3)
            
        except Exception as e:
            print(f"[{correlation_id}] Error in scraper: {e}")
        finally:
            await browser.close()
    
    print(f"[{correlation_id}] Scraper completed. Total projects: {len(captured_projects)}")
    
    return captured_projects

async def test_minimal_scraper():
    """Test der minimalen Scraper-Funktion"""
    projects = await scrape_gulp_fixed()
    
    print(f"\n=== Scraper Test Results ===")
    print(f"Total projects captured: {len(projects)}")
    
    if projects:
        print(f"\nFirst project example:")
        example = projects[0]
        for key, value in list(example.items())[:8]:
            print(f"  {key}: {str(value)[:100]}")
    
    # Speichere Ergebnis für Tests
    if projects:
        with open('/tmp/scraped_projects_test.json', 'w', encoding='utf-8') as f:
            json.dump(projects, f, ensure_ascii=False, indent=2)
        print(f"\nProjects saved to /tmp/scraped_projects_test.json")
    
    return projects

if __name__ == "__main__":
    result = asyncio.run(test_minimal_scraper())
