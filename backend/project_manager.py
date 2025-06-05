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
        print(f"\n[DEBUG] Verarbeite {len(projects)} Projekte")
        
        # Sicherstellen, dass wir eine Liste haben
        if not isinstance(projects, list):
            print(f"[WARNUNG] projects ist kein Array, sondern {type(projects)}")
            if isinstance(projects, dict):
                # Versuchen, ein Dictionary zu verarbeiten (z.B. wenn es ein JSON-Objekt mit einem 'projects'-Feld ist)
                if 'projects' in projects and isinstance(projects['projects'], list):
                    projects = projects['projects']
                    print(f"[DEBUG] Extrahierte {len(projects)} Projekte aus dem 'projects'-Feld")
                else:
                    # Konvertieren zu einer Liste mit einem Element
                    projects = [projects]
                    print(f"[DEBUG] Konvertierte ein einzelnes Dictionary zu einer Liste")
            else:
                # Fallback: Leere Liste
                print(f"[FEHLER] Konnte projects nicht verarbeiten, verwende leere Liste")
                projects = []
        
        history = self._load_history()
        known_project_ids = set(history["known_project_ids"])
        
        # Duplikate entfernen und neue Projekte identifizieren
        unique_projects = []
        new_projects = []
        seen_ids = set()
        
        for project in projects:
            # Sicherstellen, dass wir ein Dictionary haben
            if not isinstance(project, dict):
                print(f"[WARNUNG] Überspringe Projekt, das kein Dictionary ist: {type(project)}")
                continue
                
            project_id = project.get("id")
            
            # Wenn keine ID vorhanden ist, generieren wir eine basierend auf dem Titel und anderen Attributen
            if not project_id:
                title = project.get("title", "")
                company = project.get("company", "")
                location = project.get("location", "")
                project_id = f"{title}_{company}_{location}".replace(" ", "_")[:50]
                project["id"] = project_id
                print(f"[DEBUG] Generierte ID für Projekt ohne ID: {project_id}")
                
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
        
        print(f"[DEBUG] {len(unique_projects)} eindeutige Projekte, {len(new_projects)} neue Projekte")
        
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
        
        # Für Render: Wenn wir auf Render sind, behandeln wir alle Projekte als aktuell
        is_render = os.environ.get('RENDER', False)
        if is_render:
            print(f"[DEBUG] Render-Umgebung erkannt, behandle alle Projekte als aktuell")
            recent_projects = unique_projects
        else:
            # Normale Verarbeitung für lokale Umgebung
            for project in unique_projects:
                # Prüfen, ob das Projekt in den letzten 24 Stunden aktualisiert wurde
                # GULP-Projekte verwenden originalPublicationDate für das Datum
                updated_str = project.get("originalPublicationDate") or project.get("updated_at") or project.get("created_at")
                if updated_str:
                    try:
                        # Versuchen, das Datum zu parsen
                        try:
                            updated_at = datetime.fromisoformat(updated_str)
                        except ValueError:
                            # Fallback für andere Datumsformate
                            try:
                                updated_at = datetime.strptime(updated_str, "%Y-%m-%dT%H:%M:%S.%f")
                            except ValueError:
                                # Weitere Fallbacks für andere Datumsformate
                                try:
                                    updated_at = datetime.strptime(updated_str, "%Y-%m-%d")
                                except ValueError:
                                    # Als letzten Versuch das aktuelle Datum verwenden
                                    print(f"[WARNUNG] Konnte Datum nicht parsen für Projekt {project.get('id')}: {updated_str}")
                                    updated_at = current_time
                        
                        # Prüfen, ob das Datum in der Zukunft liegt (z.B. 2025)
                        if updated_at > current_time:
                            print(f"Projekt {project.get('id')}: Zukunftsdatum {updated_str} erkannt, als aktuell markiert")
                            recent_projects.append(project)
                            continue
                        
                        # Prüfen, ob das Projekt innerhalb der letzten 24 Stunden aktualisiert wurde
                        time_diff = current_time - updated_at
                        print(f"Projekt {project.get('id')}: Datum {updated_str}, Differenz: {time_diff.total_seconds()/3600:.2f} Stunden")
                        if time_diff.total_seconds() < 24 * 60 * 60:  # 24 Stunden in Sekunden
                            recent_projects.append(project)
                            continue
                    except (ValueError, TypeError) as e:
                        print(f"Fehler beim Parsen des Datums für Projekt {project.get('id')}: {str(e)} (Datum: {updated_str})")
                        # Wenn das Datum nicht geparst werden kann, behandeln wir es als aktuell, um keine Projekte zu verlieren
                        recent_projects.append(project)
                        continue
                else:
                    # Wenn kein Datum vorhanden ist, behandeln wir es als aktuell
                    print(f"Projekt {project.get('id')}: Kein Datum vorhanden, als aktuell markiert")
                    recent_projects.append(project)
                    continue
                    
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
    
    def get_archive_count(self) -> int:
        """Gibt die Anzahl der archivierten Projekte zurück."""
        archive_projects = self._load_archive_projects()
        return len(archive_projects)
    
    def get_archive_projects(self, page: int = 1, limit: int = 10) -> Tuple[List[Dict], int]:
        """Gibt die archivierten Projekte mit Paginierung zurück."""
        archive_projects = self._load_archive_projects()
        
        # Berechnen des Paginierungs-Offsets
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        
        return archive_projects[start_idx:end_idx], len(archive_projects)
    
    def get_projects(self, page: int = 1, limit: int = 10, search: str = None, 
                location: str = None, remote: bool = None, archived: bool = False,
                include_new_only: bool = False, show_all: bool = False, force_reprocess: bool = False) -> Tuple[List[Dict], int]:
        """Gibt Projekte mit Filterung und Paginierung zurück.
        
        Args:
            page: Seitennummer für die Paginierung
            limit: Anzahl der Projekte pro Seite
            search: Suchbegriff für Titel, Beschreibung und Firma
            location: Suchbegriff für den Standort
            remote: Filter für Remote-Status
            archived: Wenn True, werden archivierte Projekte zurückgegeben, sonst aktuelle
            include_new_only: Wenn True, werden nur neue Projekte zurückgegeben
            show_all: Wenn True, werden alle Projekte (aktuell und archiviert) zurückgegeben
            force_reprocess: Wenn True, werden die Rohdaten neu verarbeitet (für Render wichtig)
            
        Returns:
            Tuple mit paginierten Projekten und Gesamtanzahl
        """
        try:
            print(f"\n[DEBUG] get_projects aufgerufen mit: archived={archived}, show_all={show_all}, include_new_only={include_new_only}, force_reprocess={force_reprocess}")
            
            # Prüfen, ob die Projektdateien existieren
            print(f"[DEBUG] Projektdateien: recent={self.recent_projects_file.exists()}, archive={self.archive_projects_file.exists()}, raw={self.projects_file.exists()}")
            
            # Für Render: Wenn wir auf Render sind, versuchen wir immer zuerst die Rohdaten zu laden
            is_render = os.environ.get('RENDER', False)
            if is_render and self.projects_file.exists():
                print(f"[DEBUG] Render-Umgebung erkannt, lade Rohdaten direkt")
                try:
                    raw_projects = json.loads(self.projects_file.read_text(encoding="utf-8"))
                    print(f"[DEBUG] {len(raw_projects)} Rohdaten-Projekte geladen")
                    
                    # Wenn show_all oder archived nicht gesetzt ist, verarbeite die Projekte neu
                    if force_reprocess or not (self.recent_projects_file.exists() and self.archive_projects_file.exists()):
                        print(f"[DEBUG] Verarbeite Projekte neu für Render")
                        self.process_projects(raw_projects)
                    
                    # Für Render: Wenn show_all aktiviert ist oder keine spezifische Anfrage, gib alle Projekte zurück
                    if show_all or (not archived and not include_new_only):
                        print(f"[DEBUG] Render: Gebe alle {len(raw_projects)} Projekte zurück")
                        return self._apply_filters_and_pagination(raw_projects, page, limit, search, location, remote, include_new_only)
                except Exception as e:
                    print(f"[DEBUG] Fehler beim Laden der Rohdaten auf Render: {str(e)}")
            
            # Wenn force_reprocess aktiviert ist oder die Projektdatei existiert, aber keine recent oder archive Dateien,
            # versuchen wir die Projekte neu zu verarbeiten
            if force_reprocess or (self.projects_file.exists() and (not self.recent_projects_file.exists() or not self.archive_projects_file.exists())):
                print(f"[DEBUG] Projektdateien fehlen oder force_reprocess aktiviert, versuche Neuverarbeitung der Rohdaten")
                try:
                    if self.projects_file.exists():
                        raw_projects = json.loads(self.projects_file.read_text(encoding="utf-8"))
                        print(f"[DEBUG] {len(raw_projects)} Rohdaten-Projekte geladen, verarbeite neu...")
                        self.process_projects(raw_projects)
                        print(f"[DEBUG] Neuverarbeitung abgeschlossen")
                except Exception as e:
                    print(f"[DEBUG] Fehler bei Neuverarbeitung: {str(e)}")
            
            # Laden der Projekte basierend auf den Parametern
            if show_all:
                print(f"[DEBUG] Lade ALLE Projekte (aktuell + archiviert)")
                # Alle Projekte laden (archiviert und aktuell)
                archive_projects = self._load_archive_projects()
                recent_projects = []
                
                if self.recent_projects_file.exists():
                    try:
                        recent_projects = json.loads(self.recent_projects_file.read_text(encoding="utf-8"))
                        print(f"[DEBUG] {len(recent_projects)} aktuelle Projekte geladen")
                    except Exception as e:
                        print(f"[DEBUG] Fehler beim Laden aktueller Projekte: {str(e)}")
                else:
                    print(f"[DEBUG] Keine aktuellen Projekte gefunden")
                    
                print(f"[DEBUG] {len(archive_projects)} archivierte Projekte geladen")
                
                # Combine projects, avoiding duplicates by ID
                project_dict = {}
                for project in recent_projects + archive_projects:
                    if project.get("id"):
                        project_dict[project.get("id")] = project
                projects = list(project_dict.values())
                print(f"[DEBUG] {len(projects)} kombinierte Projekte nach Deduplizierung")
                
                # Wenn keine Projekte gefunden wurden, versuchen wir direkt aus der Rohdatei zu laden
                if not projects and self.projects_file.exists():
                    print(f"[DEBUG] Keine kombinierten Projekte, versuche Rohdaten")
                    try:
                        raw_projects = json.loads(self.projects_file.read_text(encoding="utf-8"))
                        print(f"[DEBUG] {len(raw_projects)} Projekte direkt aus Rohdaten geladen")
                        projects = raw_projects
                    except Exception as e:
                        print(f"[DEBUG] Fehler beim Laden aus Rohdaten: {str(e)}")
            elif archived:
                # Archivierte Projekte laden
                projects = self._load_archive_projects()
            else:
                # Aktuelle Projekte laden
                if self.recent_projects_file.exists():
                    projects = json.loads(self.recent_projects_file.read_text(encoding="utf-8"))
                else:
                    projects = []
            
            # Filterung anwenden
            filtered_projects = projects
            
            # Nur neue Projekte anzeigen, wenn gewünscht
            if include_new_only and not archived:
                new_project_ids = {p.get("id") for p in self.get_new_projects()}
                filtered_projects = [p for p in filtered_projects if p.get("id") in new_project_ids]
            
            # Nach Suchbegriff filtern - erweiterte Suche mit Skills und besserer Genauigkeit
            if search and search.strip():
                search_terms = search.lower().split()
                projects_with_scores = []
                
                for project in filtered_projects:
                    # Initialisiere Score für dieses Projekt
                    score = 0
                    
                    # Prüfe Titel (höchste Gewichtung)
                    title = project.get("title", "").lower()
                    for term in search_terms:
                        if term in title:
                            score += 3
                    
                    # Prüfe Beschreibung
                    description = project.get("description", "").lower()
                    for term in search_terms:
                        if term in description:
                            score += 1
                    
                    # Prüfe Firma
                    company = project.get("companyName", "").lower()
                    for term in search_terms:
                        if term in company:
                            score += 2
                    
                    # Prüfe Skills (wichtig für Technologien)
                    skills = project.get("skills", [])
                    if isinstance(skills, list):
                        skills_text = " ".join([str(skill).lower() for skill in skills])
                        for term in search_terms:
                            if term in skills_text:
                                score += 3
                    elif isinstance(skills, str):
                        skills_text = skills.lower()
                        for term in search_terms:
                            if term in skills_text:
                                score += 3
                    
                    # Wenn mindestens ein Suchbegriff gefunden wurde, füge das Projekt mit Score hinzu
                    if score > 0:
                        projects_with_scores.append((project, score))
                
                # Sortiere Projekte nach Relevanz (höchster Score zuerst)
                projects_with_scores.sort(key=lambda x: x[1], reverse=True)
                
                # Aktualisiere die gefilterten Projekte mit den sortierten Ergebnissen
                filtered_projects = [project for project, _ in projects_with_scores]
            
            # Nach Standort filtern
            if location and location.strip():
                location_lower = location.lower()
                filtered_projects = [p for p in filtered_projects if 
                                   location_lower in p.get("location", "").lower()]
            
            # Nach Remote-Status filtern
            if remote is not None:
                filtered_projects = [p for p in filtered_projects if 
                                   p.get("remote") == remote]
            
            # Gesamtanzahl der gefilterten Projekte speichern
            total_count = len(filtered_projects)
            
            # Paginierung anwenden
            start_idx = (page - 1) * limit
            end_idx = start_idx + limit
            paginated_projects = filtered_projects[start_idx:end_idx]
            
            return paginated_projects, total_count
            
        except Exception as e:
            print(f"Fehler beim Abrufen der Projekte: {str(e)}")
            return [], 0
