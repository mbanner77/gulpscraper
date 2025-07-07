#!/usr/bin/env python3
"""
Teste die neue GULP API um sicherzustellen, dass sie funktioniert
"""

import asyncio
import json
from playwright.async_api import async_playwright

async def test_new_gulp_api():
    print("=== Teste neue GULP API ===")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        # Sammle API-Requests
        captured_requests = []
        
        async def handle_request(request):
            if 'projects' in request.url and ('search' in request.url or 'jobs' in request.url):
                print(f"API Request: {request.url}")
                captured_requests.append(request.url)
        
        async def handle_response(response):
            if 'projects' in response.url and 'search' in response.url:
                print(f"API Response: {response.url} - Status: {response.status}")
                if response.status == 200:
                    try:
                        data = await response.json()
                        print(f"Response data keys: {data.keys() if isinstance(data, dict) else 'not dict'}")
                        if isinstance(data, dict) and 'data' in data:
                            projects = data.get('data', [])
                            print(f"Found {len(projects)} projects")
                            if projects:
                                # Zeige erstes Projekt als Beispiel
                                first_project = projects[0]
                                print(f"Example project: {first_project.get('title', 'no title')} - {first_project.get('id', 'no id')}")
                    except Exception as e:
                        print(f"Error parsing response: {e}")
        
        page.on("request", handle_request)
        page.on("response", handle_response)
        
        # Lade die Projektseite
        print("Loading project page...")
        try:
            await page.goto("https://www.gulp.de/gulp2/g/projekte", wait_until="networkidle", timeout=30000)
            print(f"Page loaded successfully: {page.url}")
            
            # Warte auf API-Calls
            await asyncio.sleep(5)
            
            # Prüfe Seiteninhalt
            title = await page.title()
            print(f"Page title: {title}")
            
        except Exception as e:
            print(f"Error loading page: {e}")
        
        await browser.close()
        
        print(f"\nCaptured {len(captured_requests)} API requests:")
        for req in captured_requests:
            print(f"  - {req}")

if __name__ == "__main__":
    asyncio.run(test_new_gulp_api())
