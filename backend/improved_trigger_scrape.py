"""
Verbesserte trigger_scrape-Funktion für den GULP Scraper
Diese Datei enthält eine überarbeitete Version der trigger_scrape-Funktion,
die speziell für die Render-Umgebung optimiert ist.
"""

import os
import json
import datetime
from pathlib import Path
from typing import List, Dict
from fastapi import BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Import des Render-Helpers
from render_helper import handle_render_scrape, update_last_scrape_time

# Pfade für Daten
DATA_DIR = Path("./data")
OUTPUT_JSON = DATA_DIR / "projects.json"
LAST_SCRAPE_FILE = DATA_DIR / "last_scrape.txt"

# Bestimme, ob wir in einer Cloud-Umgebung (z.B. Render) laufen
IS_CLOUD_ENV = os.environ.get('RENDER', False) or os.environ.get('CLOUD_ENV', False)

# Konfiguration für den Scraper
USE_REAL_SCRAPER = os.environ.get('USE_REAL_SCRAPER', 'False').lower() == 'true'
if IS_CLOUD_ENV and not os.environ.get('USE_REAL_SCRAPER'):
    USE_REAL_SCRAPER = False
    print(f"[CONFIG] Render-Umgebung erkannt, setze USE_REAL_SCRAPER=False")

# ScrapeRequest-Modell (muss mit dem Original übereinstimmen)
class ScrapeRequest(BaseModel):
    pages: List[int] = []
    send_email: bool = False

# Verbesserte trigger_scrape-Funktion
async def improved_trigger_scrape(
    background_tasks: BackgroundTasks,
    request: ScrapeRequest = ScrapeRequest(),
    app=None,  # FastAPI-App
    is_scraping=False,  # Globale Variable aus scraper.py
    email_notification_enabled=False,  # Globale Variable aus scraper.py
    email_recipient="",  # Globale Variable aus scraper.py
    project_manager=None,  # ProjectManager-Instanz aus scraper.py
    email_service=None,  # EmailService-Instanz aus scraper.py
    scrape_gulp=None,  # scrape_gulp-Funktion aus scraper.py
    PAGE_RANGE=range(1, 2)  # PAGE_RANGE aus scraper.py
):
    """Trigger a new scrape with improved Render compatibility."""
    # Globale Variablen müssen in der aufrufenden Funktion aktualisiert werden
    
    if is_scraping:
        return JSONResponse(
            status_code=409,
            content={"error": "A scrape is already in progress"}
        )
    
    print(f"\n[MANUAL SCRAPE] Manueller Scrape-Vorgang gestartet")
    print(f"[MANUAL SCRAPE] Umgebung: {'Render/Cloud' if IS_CLOUD_ENV else 'Lokal'}")
    print(f"[MANUAL SCRAPE] USE_REAL_SCRAPER={USE_REAL_SCRAPER}")
    
    # Convert the pages list to a range if provided
    pages = PAGE_RANGE
    if request.pages:
        pages = range(min(request.pages), max(request.pages) + 1)
    
    # Aktiviere E-Mail-Benachrichtigung für diesen Scrape-Vorgang, wenn angefordert
    local_email_notification_enabled = request.send_email
    
    # Direkter Scrape statt Hintergrundaufgabe, um sofortige Rückmeldung zu ermöglichen
    try:
        # Starte den Scrape-Vorgang direkt
        print(f"[MANUAL SCRAPE] Führe Scrape direkt aus...")
        
        # Auf Render verwenden wir immer den Render-Helper, wenn nicht explizit anders konfiguriert
        if IS_CLOUD_ENV and not USE_REAL_SCRAPER:
            print(f"[MANUAL SCRAPE] Render-Umgebung erkannt, verwende Render-Helper")
            
            # Verwende den Render-Helper für zuverlässiges Scraping auf Render
            unique_projects, new_projects = handle_render_scrape(project_manager)
            
            # Aktualisiere den Zeitstempel des letzten Scans
            last_scrape_time = update_last_scrape_time()
            
            # Sende E-Mail-Benachrichtigung, wenn aktiviert und neue Projekte gefunden wurden
            if local_email_notification_enabled and email_recipient and new_projects and email_service:
                try:
                    print(f"\n[MANUAL SCRAPE] Versuche E-Mail-Benachrichtigung zu senden...")
                    success = email_service.send_new_projects_notification(
                        recipient=email_recipient,
                        new_projects=new_projects,
                        scan_time=datetime.datetime.now()
                    )
                    print(f"[MANUAL SCRAPE] E-Mail-Versand Ergebnis: {'Erfolgreich' if success else 'Fehlgeschlagen'}")
                except Exception as e:
                    print(f"[MANUAL SCRAPE] Error sending email notification: {str(e)}")
            
            return {
                "message": "Scrape mit Render-Helper wurde erfolgreich durchgeführt",
                "success": True,
                "last_scrape": last_scrape_time,
                "project_count": len(unique_projects),
                "new_project_count": len(new_projects),
                "email_notification": local_email_notification_enabled and email_recipient != "",
                "dummy_data": True
            }
        
        # Normaler Scrape-Vorgang (nicht Render oder explizit USE_REAL_SCRAPER=True)
        if scrape_gulp:
            projects = await scrape_gulp(pages)
            
            # Stelle sicher, dass der letzte Scrape-Zeitpunkt aktualisiert wird
            last_scrape_time = datetime.datetime.now().isoformat()
            
            # Speichere den letzten Scrape-Zeitpunkt in einer Datei für Persistenz
            try:
                LAST_SCRAPE_FILE.write_text(last_scrape_time, encoding="utf-8")
                print(f"[MANUAL SCRAPE] Letzter Scrape-Zeitpunkt gespeichert: {last_scrape_time}")
            except Exception as e:
                print(f"[MANUAL SCRAPE] Fehler beim Speichern des letzten Scrape-Zeitpunkts: {str(e)}")
            
            # Stelle sicher, dass die Projekte korrekt verarbeitet wurden
            project_count = len(projects) if projects else 0
            new_project_count = 0
            
            # Sende E-Mail-Benachrichtigung, wenn aktiviert und neue Projekte gefunden wurden
            if local_email_notification_enabled and email_recipient and projects and email_service:
                try:
                    print(f"\n[MANUAL SCRAPE] Versuche E-Mail-Benachrichtigung zu senden...")
                    success = email_service.send_new_projects_notification(
                        recipient=email_recipient,
                        new_projects=projects,  # Hier verwenden wir alle Projekte, da wir die neuen nicht kennen
                        scan_time=datetime.datetime.now()
                    )
                    print(f"[MANUAL SCRAPE] E-Mail-Versand Ergebnis: {'Erfolgreich' if success else 'Fehlgeschlagen'}")
                except Exception as e:
                    print(f"[MANUAL SCRAPE] Error sending email notification: {str(e)}")
            
            return {
                "message": "Scrape wurde erfolgreich durchgeführt",
                "success": True,
                "last_scrape": last_scrape_time,
                "project_count": project_count,
                "new_project_count": new_project_count,
                "email_notification": local_email_notification_enabled and email_recipient != ""
            }
        else:
            return JSONResponse(
                status_code=500,
                content={
                    "error": "scrape_gulp-Funktion ist nicht verfügbar",
                    "success": False
                }
            )
    except Exception as e:
        print(f"[MANUAL SCRAPE] Fehler beim Scrapen: {str(e)}")
        import traceback
        print(f"[MANUAL SCRAPE] Traceback: {traceback.format_exc()}")
        
        # Bei Fehlern auf Render versuchen wir es mit dem Render-Helper als Fallback
        if IS_CLOUD_ENV:
            try:
                print(f"[MANUAL SCRAPE] Fehler auf Render, versuche Fallback mit Render-Helper")
                unique_projects, new_projects = handle_render_scrape(project_manager)
                last_scrape_time = update_last_scrape_time()
                
                return {
                    "message": "Scrape mit Render-Helper-Fallback wurde durchgeführt",
                    "success": True,
                    "last_scrape": last_scrape_time,
                    "project_count": len(unique_projects),
                    "new_project_count": len(new_projects),
                    "email_notification": False,
                    "dummy_data": True,
                    "fallback": True
                }
            except Exception as fallback_error:
                print(f"[MANUAL SCRAPE] Auch Fallback mit Render-Helper fehlgeschlagen: {str(fallback_error)}")
        
        return JSONResponse(
            status_code=500,
            content={
                "error": f"Fehler beim Scrapen: {str(e)}",
                "success": False
            }
        )

# Anleitung zur Integration
"""
Um diese verbesserte trigger_scrape-Funktion in die bestehende Anwendung zu integrieren,
ersetzen Sie die bestehende trigger_scrape-Funktion in scraper.py durch diese Version.

Stellen Sie sicher, dass Sie auch den render_helper.py importieren:

```python
# Am Anfang der scraper.py-Datei
from render_helper import handle_render_scrape, update_last_scrape_time
```

Und passen Sie die Parameter entsprechend an:

```python
@app.post("/scrape")
async def trigger_scrape(
    background_tasks: BackgroundTasks,
    request: ScrapeRequest = ScrapeRequest()
):
    return await improved_trigger_scrape(
        background_tasks=background_tasks,
        request=request,
        app=app,
        is_scraping=is_scraping,
        email_notification_enabled=email_notification_enabled,
        email_recipient=email_recipient,
        project_manager=project_manager,
        email_service=email_service,
        scrape_gulp=scrape_gulp,
        PAGE_RANGE=PAGE_RANGE
    )
```
"""
