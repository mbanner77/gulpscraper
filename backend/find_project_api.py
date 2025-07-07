#!/usr/bin/env python3
"""
Suche nach der aktuellen GULP Projekt-API durch Analyse der Website
"""

import asyncio
import re
from playwright.async_api import async_playwright

async def find_project_endpoints():
    print("Suche nach GULP Projekt-Endpoints...")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        # Sammle alle Netzwerk-Requests
        requests = []
        async def handle_request(request):
            if 'api' in request.url or 'rest' in request.url:
                requests.append(request.url)
                print(f"API Request gefunden: {request.url}")
        
        page.on("request", handle_request)
        
        # Teste verschiedene mögliche Seiten
        urls_to_test = [
            "https://www.gulp.de/",
            "https://www.gulp.de/gulp2/g/jobs",
            "https://www.gulp.de/freelancing",
            "https://www.gulp.de/unternehmen/freelancer-finden"
        ]
        
        for url in urls_to_test:
            print(f"\n=== Analysiere: {url} ===")
            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)
                print(f"Seite geladen: {page.url}")
                
                # Warte auf Netzwerk-Aktivität
                await asyncio.sleep(5)
                
                # Suche nach Links zu Projekten
                links = await page.query_selector_all('a[href*="projekt"]')
                for link in links[:5]:  # Max 5 links
                    href = await link.get_attribute('href')
                    text = await link.text_content()
                    print(f"Projekt-Link: {href} -> {text}")
                
            except Exception as e:
                print(f"Fehler bei {url}: {e}")
        
        await browser.close()
        
        print(f"\n=== Gefundene API-Endpoints: ===")
        unique_apis = list(set(requests))
        for api in unique_apis:
            print(f"- {api}")
        
        return unique_apis

# Teste auch manuelle API-Endpoints
async def test_manual_endpoints():
    print("\n=== Teste bekannte API-Patterns ===")
    
    import requests
    
    # Mögliche API-Endpoints basierend auf GULP-Patterns
    api_endpoints = [
        "https://www.gulp.de/gulp2/rest/internal/projects/search",
        "https://www.gulp.de/rest/internal/projects/search",
        "https://www.gulp.de/api/projects/search",
        "https://www.gulp.de/gulp2/api/projects",
        "https://www.gulp.de/gulp2/rest/projects",
        "https://www.gulp.de/gulp2/rest/cms/search-suggestions",
        "https://www.gulp.de/gulp2/rest/cms/locations"
    ]
    
    for endpoint in api_endpoints:
        try:
            response = requests.get(endpoint, timeout=10)
            print(f"{endpoint} -> Status: {response.status_code}")
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '')
                if 'json' in content_type:
                    print(f"  ✓ JSON Response ({len(response.text)} chars)")
                    # Zeige ersten Teil der Response
                    if len(response.text) < 500:
                        print(f"  Content: {response.text}")
        except Exception as e:
            print(f"{endpoint} -> Error: {e}")

async def main():
    api_endpoints = await find_project_endpoints()
    await test_manual_endpoints()

if __name__ == "__main__":
    asyncio.run(main())
