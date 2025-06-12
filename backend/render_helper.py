"""
Render Helper Module für den GULP Scraper
Enthält Hilfsfunktionen, um den Scraper auf Render zuverlässig auszuführen
"""

import os
import json
import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Any

# Bestimme, ob wir in einer Cloud-Umgebung (z.B. Render) laufen
IS_CLOUD_ENV = os.environ.get('RENDER', False) or os.environ.get('CLOUD_ENV', False)

# Pfade für Daten und Debug-Ausgaben
DATA_DIR = Path("./data")
OUTPUT_JSON = DATA_DIR / "projects.json"
LAST_SCRAPE_FILE = DATA_DIR / "last_scrape.txt"

def create_dummy_projects() -> List[Dict]:
    """
    Erstellt Dummy-Projekte für die Render-Umgebung
    """
    print("[RENDER_HELPER] Erstelle Dummy-Projekte für Render")
    
    # Erstelle ein einfaches Dummy-Projekt mit aktuellem Zeitstempel
    dummy_projects = [
        {
            "id": f"dummy-1-{datetime.datetime.now().strftime('%Y%m%d%H%M')}",
            "title": "Dummy Projekt 1",
            "description": "Dies ist ein automatisch erstelltes Dummy-Projekt für Render.",
            "companyName": "Dummy GmbH",
            "location": "Berlin",
            "isRemoteWorkPossible": True,
            "publicationDate": datetime.datetime.now().strftime("%d.%m.%Y"),
            "originalPublicationDate": datetime.datetime.now().isoformat(),
            "url": "https://www.gulp.de/"
        },
        {
            "id": f"dummy-2-{datetime.datetime.now().strftime('%Y%m%d%H%M')}",
            "title": "Dummy Projekt 2",
            "description": "Ein weiteres automatisch erstelltes Dummy-Projekt für Render.",
            "companyName": "Test AG",
            "location": "München",
            "isRemoteWorkPossible": True,
            "publicationDate": datetime.datetime.now().strftime("%d.%m.%Y"),
            "originalPublicationDate": datetime.datetime.now().isoformat(),
            "url": "https://www.gulp.de/"
        }
    ]
    
    return dummy_projects

def save_dummy_projects(dummy_projects: List[Dict]) -> bool:
    """
    Speichert Dummy-Projekte in die Ausgabedatei
    """
    try:
        # Stelle sicher, dass das Datenverzeichnis existiert
        DATA_DIR.mkdir(exist_ok=True, parents=True)
        
        # Speichere die Dummy-Projekte
        OUTPUT_JSON.write_text(
            json.dumps(dummy_projects, indent=2, ensure_ascii=False), 
            encoding="utf-8"
        )
        print(f"[RENDER_HELPER] {len(dummy_projects)} Dummy-Projekte gespeichert in {OUTPUT_JSON}")
        return True
    except Exception as e:
        print(f"[RENDER_HELPER] Fehler beim Speichern der Dummy-Projekte: {str(e)}")
        return False

def update_last_scrape_time() -> str:
    """
    Aktualisiert den Zeitstempel des letzten Scans
    """
    last_scrape_time = datetime.datetime.now().isoformat()
    
    try:
        LAST_SCRAPE_FILE.write_text(last_scrape_time, encoding="utf-8")
        print(f"[RENDER_HELPER] Letzter Scrape-Zeitpunkt gespeichert: {last_scrape_time}")
    except Exception as e:
        print(f"[RENDER_HELPER] Fehler beim Speichern des letzten Scrape-Zeitpunkts: {str(e)}")
    
    return last_scrape_time

def handle_render_scrape(project_manager) -> Tuple[List[Dict], List[Dict]]:
    """
    Führt einen Scrape für die Render-Umgebung durch
    Erstellt Dummy-Projekte und verarbeitet sie mit dem ProjectManager
    
    Returns:
        Tuple[List[Dict], List[Dict]]: (unique_projects, new_projects)
    """
    if not IS_CLOUD_ENV:
        print("[RENDER_HELPER] Nicht in Render-Umgebung, überspringe Render-spezifischen Scrape")
        return [], []
    
    print("[RENDER_HELPER] Führe Render-spezifischen Scrape durch")
    
    # Erstelle Dummy-Projekte
    dummy_projects = create_dummy_projects()
    
    # Speichere die Dummy-Projekte
    save_dummy_projects(dummy_projects)
    
    # Aktualisiere den Zeitstempel des letzten Scans
    update_last_scrape_time()
    
    # Verarbeite die Dummy-Projekte mit dem ProjectManager
    if project_manager:
        unique_projects, new_projects = project_manager.process_projects(dummy_projects)
        print(f"[RENDER_HELPER] {len(unique_projects)} eindeutige Projekte, {len(new_projects)} neue Projekte")
        
        # Erzwinge eine Neusortierung der Projekte (aktuell vs. archiviert)
        project_manager.get_projects(force_reprocess=True, show_all=True)
        
        return unique_projects, new_projects
    else:
        print("[RENDER_HELPER] ProjectManager nicht verfügbar")
        return dummy_projects, dummy_projects
