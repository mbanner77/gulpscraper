#!/usr/bin/env python3
"""
Teste die neuen GULP URLs mit Playwright um herauszufinden, welche funktioniert
"""

import asyncio
import requests
from playwright.async_api import async_playwright

async def test_playwright_urls():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        # URLs zum testen
        urls_to_test = [
            "https://www.gulp.de/projektmarkt",
            "https://www.gulp.de/gulp2/g/projekte?page=1",
            "https://www.gulp.de/gulp2/home/project"
        ]
        
        for url in urls_to_test:
            print(f"\n=== Testing URL: {url} ===")
            try:
                response = await page.goto(url, wait_until="networkidle", timeout=30000)
                print(f"Status: {response.status}")
                print(f"URL after redirects: {page.url}")
                
                # Check page title and content
                title = await page.title()
                print(f"Title: {title}")
                
                # Look for project-related content
                content = await page.content()
                if "projekt" in content.lower():
                    print("✓ Contains 'projekt'")
                if "freelancer" in content.lower():
                    print("✓ Contains 'freelancer'")
                if len(content) > 50000:
                    print(f"✓ Rich content ({len(content)} chars)")
                
                # Look for project containers/elements
                project_elements = await page.query_selector_all('[data-project-id], .project, .card-project, [id*="project"], [class*="project"]')
                print(f"Found {len(project_elements)} potential project elements")
                
                # Check for API calls in network
                print("Waiting for network activity...")
                await asyncio.sleep(3)
                
            except Exception as e:
                print(f"Error loading {url}: {e}")
        
        await browser.close()

# Run the test
if __name__ == "__main__":
    asyncio.run(test_playwright_urls())
