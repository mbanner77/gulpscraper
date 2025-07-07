#!/usr/bin/env python3
"""
Teste einen funktionierenden Scraper mit der neuen GULP API
"""

import asyncio
import json
import re
from playwright.async_api import async_playwright

# Updated API pattern for new GULP structure
API_RE = re.compile(r'/rest/internal/projects/search')

async def test_working_scraper():
    print("=== Teste funktionierenden Scraper mit neuer API ===")
    
    captured_data = []
    
    async def process_api_response(response):
        """Process API responses and capture project data"""
        if response and API_RE.search(response.url):
            print(f"Processing API response: {response.url}")
            try:
                if response.status == 200:
                    data = await response.json()
                    print(f"API Response successful - Keys: {data.keys()}")
                    
                    if 'projects' in data:
                        projects = data['projects']
                        print(f"Found {len(projects)} projects in API response")
                        captured_data.extend(projects)
                        
                        # Zeige einige Beispiel-Projekte
                        for i, project in enumerate(projects[:3]):
                            print(f"Project {i+1}: {project.get('title', 'No title')} - ID: {project.get('id', 'No ID')}")
                    
                    return data
            except Exception as e:
                print(f"Error processing API response: {e}")
        return None
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        # Handle responses
        page.on("response", process_api_response)
        
        try:
            print("Loading GULP project page...")
            # Verwende direkte API-Aufrufe statt Page-Navigation
            
            # Option 1: Versuche Seite zu laden (mit kürzerem Timeout)
            try:
                await page.goto("https://www.gulp.de/gulp2/g/projekte", timeout=15000)
                print("Page loaded successfully")
                await asyncio.sleep(3)  # Warte auf API-Calls
            except Exception as e:
                print(f"Page load timeout, but API calls may still work: {e}")
            
            # Option 2: Direkte API-Aufrufe (falls verfügbar)
            # Teste ob wir die API direkt aufrufen können
            try:
                api_response = await page.evaluate("""
                    fetch('/gulp2/rest/internal/projects/search', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({})
                    }).then(r => r.json()).catch(e => ({error: e.message}))
                """)
                print(f"Direct API call result: {api_response}")
            except Exception as e:
                print(f"Direct API call failed: {e}")
                
        except Exception as e:
            print(f"Error in scraper test: {e}")
        
        await browser.close()
        
        print(f"\nScraper Test Results:")
        print(f"Total projects captured: {len(captured_data)}")
        
        if captured_data:
            print("\nExample captured project structure:")
            example = captured_data[0]
            for key, value in list(example.items())[:5]:
                print(f"  {key}: {str(value)[:100]}...")
        
        return captured_data

if __name__ == "__main__":
    result = asyncio.run(test_working_scraper())
