"""
E-Mail-Service für GULP Job Scraper
===================================
Dieser Service versendet E-Mail-Benachrichtigungen über neue Projekte.
"""

import os
import emails
import traceback
from emails.template import JinjaTemplate
from typing import List, Dict, Optional, Any
from datetime import datetime
from pathlib import Path
import json
import socket

# E-Mail-Konfiguration
DEFAULT_SENDER = "GULP Job Scraper <noreply@example.com>"
EMAIL_TEMPLATE_DIR = Path(__file__).parent / "email_templates"


class EmailService:
    """Service zum Versenden von E-Mail-Benachrichtigungen."""
    
    def __init__(
        self,
        smtp_host: str = None,
        smtp_port: int = None,
        smtp_user: str = None,
        smtp_password: str = None,
        sender: str = None,
        frontend_url: str = None
    ):
        """Initialisiert den E-Mail-Service mit SMTP-Konfiguration."""
        self.smtp_host = smtp_host or os.environ.get("SMTP_HOST")
        self.smtp_port = smtp_port or int(os.environ.get("SMTP_PORT", 587))
        self.smtp_user = smtp_user or os.environ.get("SMTP_USER")
        self.smtp_password = smtp_password or os.environ.get("SMTP_PASSWORD")
        self.sender = sender or os.environ.get("EMAIL_SENDER", DEFAULT_SENDER)
        self.frontend_url = frontend_url or os.environ.get("FRONTEND_URL", "http://localhost")
        
        # Prüfen, ob die SMTP-Konfiguration vollständig ist
        self.is_configured = all([
            self.smtp_host,
            self.smtp_port,
            self.smtp_user,
            self.smtp_password
        ])
        
        # E-Mail-Template laden
        self.new_projects_template_path = EMAIL_TEMPLATE_DIR / "new_projects.html"
        try:
            with open(self.new_projects_template_path, 'r', encoding='utf-8') as f:
                self.new_projects_template = f.read()
        except Exception as e:
            print(f"Fehler beim Laden des E-Mail-Templates: {str(e)}")
            self.new_projects_template = "<h1>Neue GULP Projekte gefunden</h1><p>Es wurden {{new_projects|length}} neue Projekte gefunden.</p>"
    
    def send_new_projects_notification(
        self,
        recipient: str,
        new_projects: List[Dict],
        scan_time: Optional[datetime] = None
    ) -> bool:
        """Sendet eine E-Mail-Benachrichtigung über neue Projekte."""
        try:
            # Ausführliche Debug-Informationen
            print("\n--- E-MAIL VERSAND START ---")
            print(f"Hostname: {socket.gethostname()}")
            print(f"Umgebungsvariablen: SMTP_HOST={os.environ.get('SMTP_HOST')}, SMTP_PORT={os.environ.get('SMTP_PORT')}")
            print(f"Konfiguration: {self.get_config_status()}")
            
            if not self.is_configured:
                print("E-Mail-Service ist nicht konfiguriert. Keine E-Mail gesendet.")
                print("Fehlende Konfiguration:")
                if not self.smtp_host: print("- SMTP_HOST fehlt")
                if not self.smtp_port: print("- SMTP_PORT fehlt")
                if not self.smtp_user: print("- SMTP_USER fehlt")
                if not self.smtp_password: print("- SMTP_PASSWORD fehlt")
                return False
            
            if not new_projects:
                print("Keine neuen Projekte gefunden. Keine E-Mail gesendet.")
                return False
            
            if scan_time is None:
                scan_time = datetime.now()
            
            # E-Mail erstellen
            message = emails.html(
                html=JinjaTemplate(self.new_projects_template),
                subject=f"GULP Job Scraper: {len(new_projects)} neue Projekte gefunden",
                mail_from=self.sender
            )
            
            # E-Mail-Kontext
            context = {
                "new_projects": new_projects,
                "scan_time": scan_time.strftime("%d.%m.%Y %H:%M:%S"),
                "frontend_url": self.frontend_url
            }
            
            # E-Mail senden
            # Port 465 verwendet SSL, Port 587 verwendet TLS
            use_ssl = self.smtp_port == 465
            use_tls = self.smtp_port == 587
            
            smtp_options = {
                "host": self.smtp_host,
                "port": self.smtp_port,
                "user": self.smtp_user,
                "password": "*****",  # Passwort nicht im Log anzeigen
                "ssl": use_ssl,
                "tls": use_tls
            }
            
            print(f"Sende E-Mail über {self.smtp_host}:{self.smtp_port} mit {'SSL' if use_ssl else 'TLS' if use_tls else 'keine Verschlüsselung'}")
            print(f"Empfänger: {recipient}")
            print(f"Absender: {self.sender}")
            print(f"Betreff: GULP Job Scraper: {len(new_projects)} neue Projekte gefunden")
            
            # Tatsächliche SMTP-Optionen für den Versand (mit echtem Passwort)
            real_smtp_options = {
                "host": self.smtp_host,
                "port": self.smtp_port,
                "user": self.smtp_user,
                "password": self.smtp_password,
                "ssl": use_ssl,
                "tls": use_tls,
                # Zusätzliche Optionen für bessere Kompatibilität
                "timeout": 30,  # Erhöhtes Timeout
                "debug": True   # Debug-Modus aktivieren
            }
            
            try:
                response = message.send(
                    to=recipient,
                    render=context,
                    smtp=real_smtp_options
                )
                
                print(f"SMTP-Antwort: {response}")
                print(f"Status-Code: {response.status_code}")
                
                success = response.status_code == 250
                if success:
                    print(f"E-Mail erfolgreich an {recipient} gesendet.")
                else:
                    print(f"Fehler beim Senden der E-Mail: {response.status_code}")
                    if hasattr(response, 'error') and response.error:
                        print(f"Fehlerdetails: {response.error}")
                
                print("--- E-MAIL VERSAND ENDE ---\n")
                return success
                
            except Exception as e:
                print(f"Exception beim E-Mail-Versand: {str(e)}")
                print(f"Traceback: {traceback.format_exc()}")
                print("--- E-MAIL VERSAND ENDE (MIT FEHLER) ---\n")
                return False
                
        except Exception as outer_e:
            print(f"Unerwarteter Fehler im E-Mail-Service: {str(outer_e)}")
            print(f"Traceback: {traceback.format_exc()}")
            print("--- E-MAIL VERSAND ENDE (MIT UNBEHANDELTEM FEHLER) ---\n")
            return False
    
    def get_config_status(self) -> Dict[str, Any]:
        """Gibt den Status der E-Mail-Konfiguration zurück."""
        return {
            "is_configured": self.is_configured,
            "smtp_host": self.smtp_host,
            "smtp_port": self.smtp_port,
            "smtp_user": self.smtp_user,
            "smtp_password_set": bool(self.smtp_password),
            "sender": self.sender,
            "frontend_url": self.frontend_url,
            "template_loaded": bool(self.new_projects_template),
            "hostname": socket.gethostname(),
            "environment": "render" if os.environ.get('RENDER') else "local"
        }
