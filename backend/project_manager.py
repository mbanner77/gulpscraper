"""
Projekt-Manager für GULP Job Scraper
===================================
Dieser Manager verwaltet die Projekte, erkennt Duplikate und identifiziert neue Projekte.
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Tuple, Set, Optional
from datetime import datetime


class ProjectManager:
    """Manager für die Verwaltung von GULP-Projekten."""
    
    def __init__(self, data_dir: Path):
        """Initialisiert den Projekt-Manager mit dem Datenverzeichnis."""
        self.data_dir = data_dir
        self.projects_file = data_dir / "gulp_projekte_raw.json"
        self.history_file = data_dir / "project_history.json"
        self.new_projects_file = data_dir / "new_projects.json"
        
        # Stellen Sie sicher, dass das Datenverzeichnis existiert
        self.data_dir.mkdir(exist_ok=True)
        
        # Initialisieren Sie die Projekthistorie, falls sie noch nicht existiert
        if not self.history_file.exists():
            self._save_history({
                "last_scan": None,
                "known_project_ids": [],
                "total_projects_found": 0
            })
    
    def _load_projects(self) -> List[Dict]:
        """Lädt die aktuellen Projekte aus der Datei."""
        if not self.projects_file.exists():
            return []
        
        try:
            return json.loads(self.projects_file.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Fehler beim Laden der Projekte: {str(e)}")
            return []
    
    def _load_history(self) -> Dict:
        """Lädt die Projekthistorie aus der Datei."""
        if not self.history_file.exists():
            return {
                "last_scan": None,
                "known_project_ids": [],
                "total_projects_found": 0
            }
        
        try:
            return json.loads(self.history_file.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Fehler beim Laden der Projekthistorie: {str(e)}")
            return {
                "last_scan": None,
                "known_project_ids": [],
                "total_projects_found": 0
            }
    
    def _save_history(self, history: Dict) -> None:
        """Speichert die Projekthistorie in der Datei."""
        try:
            self.history_file.write_text(
                json.dumps(history, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
        except Exception as e:
            print(f"Fehler beim Speichern der Projekthistorie: {str(e)}")
    
    def _save_new_projects(self, projects: List[Dict]) -> None:
        """Speichert die neuen Projekte in einer separaten Datei."""
        try:
            self.new_projects_file.write_text(
                json.dumps(projects, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
        except Exception as e:
            print(f"Fehler beim Speichern der neuen Projekte: {str(e)}")
    
    def process_projects(self, projects: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """
        Verarbeitet die gescrapten Projekte, erkennt Duplikate und identifiziert neue Projekte.
        
        Returns:
            Tuple[List[Dict], List[Dict]]: (Alle Projekte ohne Duplikate, Nur neue Projekte)
        """
        history = self._load_history()
        known_project_ids = set(history["known_project_ids"])
        
        # Duplikate entfernen und neue Projekte identifizieren
        unique_projects = []
        new_projects = []
        seen_ids = set()
        
        for project in projects:
            project_id = project.get("id")
            
            # Wenn das Projekt keine ID hat, generieren wir eine
            if not project_id:
                title = project.get("title", "")
                company = project.get("companyName", "")
                project_id = f"{title}_{company}".replace(" ", "_").lower()
                project["id"] = project_id
            
            # Duplikate innerhalb des aktuellen Scrape-Durchlaufs überspringen
            if project_id in seen_ids:
                continue
            
            seen_ids.add(project_id)
            unique_projects.append(project)
            
            # Prüfen, ob das Projekt neu ist
            if project_id not in known_project_ids:
                new_projects.append(project)
                known_project_ids.add(project_id)
        
        # Historie aktualisieren
        history["last_scan"] = datetime.now().isoformat()
        history["known_project_ids"] = list(known_project_ids)
        history["total_projects_found"] = len(known_project_ids)
        
        # Speichern
        self._save_history(history)
        
        # Wenn neue Projekte gefunden wurden, speichern wir sie separat
        if new_projects:
            self._save_new_projects(new_projects)
        
        return unique_projects, new_projects
    
    def get_new_projects(self) -> List[Dict]:
        """Gibt die zuletzt gefundenen neuen Projekte zurück."""
        if not self.new_projects_file.exists():
            return []
        
        try:
            return json.loads(self.new_projects_file.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Fehler beim Laden der neuen Projekte: {str(e)}")
            return []
    
    def get_history(self) -> Dict:
        """Gibt die Projekthistorie zurück."""
        return self._load_history()
    
    def mark_projects_as_seen(self, project_ids: List[str]) -> None:
        """Markiert Projekte als gesehen (nicht mehr neu)."""
        if not project_ids:
            return
        
        new_projects = self.get_new_projects()
        remaining_projects = [p for p in new_projects if p.get("id") not in project_ids]
        
        self._save_new_projects(remaining_projects)
