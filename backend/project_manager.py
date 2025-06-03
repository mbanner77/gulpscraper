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
        self.recent_projects_file = data_dir / "recent_projects.json"
        self.archive_projects_file = data_dir / "archive_projects.json"
        
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
    
    def _load_archive_projects(self) -> List[Dict]:
        """Lädt die Archiv-Projekte aus der Datei."""
        if not self.archive_projects_file.exists():
            return []
        
        try:
            return json.loads(self.archive_projects_file.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Fehler beim Laden der Archiv-Projekte: {str(e)}")
            return []
    
    def _update_archive_projects(self, projects: List[Dict]) -> None:
        """Aktualisiert die Archiv-Projekte in der Datei."""
        existing_archive = self._load_archive_projects()
        updated_archive = existing_archive + projects
        
        try:
            self.archive_projects_file.write_text(
                json.dumps(updated_archive, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
        except Exception as e:
            print(f"Fehler beim Aktualisieren der Archiv-Projekte: {str(e)}")
    
    def _save_recent_projects(self, projects: List[Dict]) -> None:
        """Speichert die aktuellen Projekte in einer separaten Datei."""
        try:
            self.recent_projects_file.write_text(
                json.dumps(projects, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
        except Exception as e:
            print(f"Fehler beim Speichern der aktuellen Projekte: {str(e)}")
    
    def process_projects(self, projects: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """
        Verarbeitet die gescrapten Projekte, erkennt Duplikate und identifiziert neue Projekte.
        Trennt Projekte in aktuelle (letzte 24 Stunden) und Archiv-Projekte.
        
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
            
            # Überspringen, wenn keine ID vorhanden ist
            if not project_id:
                continue
                
            # Überspringen, wenn wir dieses Projekt bereits in diesem Durchlauf gesehen haben
            if project_id in seen_ids:
                continue
                
            # Projekt als gesehen markieren
            seen_ids.add(project_id)
            
            # Projekt zu den eindeutigen Projekten hinzufügen
            unique_projects.append(project)
            
            # Prüfen, ob es sich um ein neues Projekt handelt
            if project_id not in known_project_ids:
                new_projects.append(project)
                known_project_ids.add(project_id)
        
        # Projekthistorie aktualisieren
        current_time = datetime.now()
        history["last_scan"] = current_time.isoformat()
        history["known_project_ids"] = list(known_project_ids)
        history["total_projects_found"] = len(known_project_ids)
        
        # Speichern der aktualisierten Daten
        self._save_history(history)
        self._save_new_projects(new_projects)
        
        # Trennen der Projekte in aktuelle (letzte 24 Stunden) und Archiv-Projekte
        recent_projects = []
        archive_projects = []
        
        # Laden der bestehenden Archiv-Projekte
        existing_archive = self._load_archive_projects()
        archive_ids = {p.get("id") for p in existing_archive if p.get("id")}
        
        for project in unique_projects:
            # Prüfen, ob das Projekt in den letzten 24 Stunden aktualisiert wurde
            updated_str = project.get("updated_at") or project.get("created_at")
            if updated_str:
                try:
                    updated_at = datetime.fromisoformat(updated_str)
                    time_diff = current_time - updated_at
                    if time_diff.total_seconds() < 24 * 60 * 60:  # 24 Stunden in Sekunden
                        recent_projects.append(project)
                        continue
                except (ValueError, TypeError):
                    pass  # Wenn das Datum nicht geparst werden kann, behandeln wir es als alt
            
            # Wenn das Projekt nicht aktuell ist, fügen wir es zum Archiv hinzu
            if project.get("id") not in archive_ids:
                archive_projects.append(project)
        
        # Aktualisieren des Archivs mit neuen Archiv-Projekten
        if archive_projects:
            self._update_archive_projects(archive_projects)
        
        # Speichern der aktuellen Projekte
        self._save_recent_projects(recent_projects)
        
        # Speichern der Projekte in der Hauptdatei
        try:
            self.projects_file.write_text(
                json.dumps(unique_projects, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
        except Exception as e:
            print(f"Fehler beim Speichern der Projekte: {str(e)}")
        
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
