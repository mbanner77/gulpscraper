#!/usr/bin/env python3
"""
Debug-Skript zum Testen der GULP-Website-Erreichbarkeit und Scraping-Funktion
"""

import asyncio
import json
import re
import requests
from pathlib import Path
from playwright.async_api import async_playwright

# Konfiguration
BASE_URL = "https://www.gulp.de/gulp2/home/project"
API_RE = re.compile(r"/rest/internal/projects/search")

async def test_website_connectivity():
    """Teste die grundlegende Erreichbarkeit der GULP-Website"""
    print("=== Testing GULP Website Connectivity ===")
    
    try:
        # Test mit requests
        print(f"Testing with requests: {BASE_URL}")
        response = requests.get(BASE_URL, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Content-Type: {response.headers.get('content-type', 'unknown')}")
        print(f"Content Length: {len(response.content)} bytes")
        
        # Prüfe auf wichtige Inhalte
        content = response.text
        if "project" in content.lower():
            print("✓ Found 'project' in page content")
        else:
            print("✗ 'project' not found in page content")
            
        if "gulp" in content.lower():
            print("✓ Found 'gulp' in page content")
        else:
            print("✗ 'gulp' not found in page content")
            
        return True
        
    except Exception as e:
        print(f"✗ Connectivity test failed: {e}")
        return False

async def test_playwright_browser():
    """Teste Browser-Automatisierung mit Playwright"""
    print("\n=== Testing Playwright Browser Automation ===")
    
    try:
        async with async_playwright() as p:
            print("✓ Playwright initialized")
            
            # Browser starten
            browser = await p.chromium.launch(headless=True)
            print("✓ Browser launched")
            
            context = await browser.new_context()
            print("✓ Browser context created")
            
            page = await context.new_page()
            print("✓ Page created")
            
            # Netzwerk-Überwachung einrichten
            captured_requests = []
            
            async def handle_request(request):
                captured_requests.append(request.url)
                if API_RE.search(request.url):
                    print(f"✓ API request detected: {request.url}")
            
            page.on("request", handle_request)
            
            # Seite laden
            print(f"Loading page: {BASE_URL}")
            response = await page.goto(BASE_URL, timeout=30000)
            print(f"✓ Page loaded with status: {response.status}")
            
            # Warten auf Seiten-Content
            await page.wait_for_timeout(5000)
            
            # Prüfe Seiten-Titel
            title = await page.title()
            print(f"Page Title: {title}")
            
            # Suche nach Projekten auf der Seite
            project_elements = await page.query_selector_all('[data-testid*="project"], .project, [class*="project"]')
            print(f"Found {len(project_elements)} elements with 'project' in attributes")
            
            # Scrolle um lazy loading zu triggern
            print("Scrolling to trigger lazy loading...")
            for i in range(3):
                await page.evaluate(f"window.scrollTo(0, {i * 1000})")
                await page.wait_for_timeout(1000)
            
            # Finale Netzwerk-Übersicht
            print(f"Total network requests captured: {len(captured_requests)}")
            api_requests = [url for url in captured_requests if API_RE.search(url)]
            print(f"API requests found: {len(api_requests)}")
            
            for api_url in api_requests:
                print(f"  - {api_url}")
            
            await browser.close()
            print("✓ Browser closed successfully")
            
            return len(api_requests) > 0
            
    except Exception as e:
        print(f"✗ Playwright test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_api_pattern():
    """Teste das API-Erkennungsmuster"""
    print("\n=== Testing API Pattern Recognition ===")
    
    test_urls = [
        "https://www.gulp.de/rest/internal/projects/search",
        "https://www.gulp.de/rest/internal/projects/search?page=1",
        "https://www.gulp.de/api/projects/search",
        "https://www.gulp.de/projects/search",
        "/rest/internal/projects/search",
    ]
    
    for url in test_urls:
        matches = bool(API_RE.search(url))
        print(f"URL: {url} -> Matches: {matches}")

async def main():
    """Hauptfunktion für alle Tests"""
    print("GULP Scraper Debug Tool")
    print("=" * 50)
    
    # Test 1: Website-Erreichbarkeit
    connectivity_ok = await test_website_connectivity()
    
    # Test 2: API-Pattern
    await test_api_pattern()
    
    # Test 3: Browser-Automatisierung (nur wenn Connectivity OK)
    if connectivity_ok:
        browser_ok = await test_playwright_browser()
        
        if browser_ok:
            print("\n🎉 All tests passed! The scraper should work.")
        else:
            print("\n⚠️  Browser automation failed. Check Playwright installation.")
    else:
        print("\n❌ Website not reachable. Check network connection.")

if __name__ == "__main__":
    asyncio.run(main())
