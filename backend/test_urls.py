#!/usr/bin/env python3
"""
Teste verschiedene GULP URLs um die richtige Projekt-Seite zu finden
"""

import requests

# Mögliche URLs für Projekte
test_urls = [
    "https://www.gulp.de/projekte",
    "https://www.gulp.de/projects", 
    "https://www.gulp.de/projekt",
    "https://www.gulp.de/freelancer-projekte",
    "https://www.gulp.de/gulp2/home/project",
    "https://www.gulp.de/projektmarkt",
    "https://www.gulp.de/project-search",
    "https://www.gulp.de/rest/internal/projects/search",
    "https://www.gulp.de/projektsuche"
]

for url in test_urls:
    try:
        response = requests.get(url, timeout=10)
        print(f"URL: {url}")
        print(f"Status: {response.status_code}")
        print(f"Content-Type: {response.headers.get('content-type', 'unknown')}")
        
        if response.status_code == 200:
            content = response.text.lower()
            if "projekt" in content and len(content) > 5000:  # Sinnvolle Seite mit Projekten
                print("✓ Likely project page found!")
                # Zeige ersten Teil des Contents
                print(f"Content preview: {response.text[:200]}...")
        print("-" * 50)
        
    except Exception as e:
        print(f"URL: {url} - Error: {e}")
        print("-" * 50)
