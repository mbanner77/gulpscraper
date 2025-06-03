"""
E-Mail-Service für GULP Job Scraper
===================================
Dieser Service versendet E-Mail-Benachrichtigungen über neue Projekte.
"""

import os
import emails
from emails.template import JinjaTemplate
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path
import json

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
        self.new_projects_template = str(EMAIL_TEMPLATE_DIR / "new_projects.html")
    
    def send_new_projects_notification(
        self,
        recipient: str,
        new_projects: List[Dict],
        scan_time: Optional[datetime] = None
    ) -> bool:
        """Sendet eine E-Mail-Benachrichtigung über neue Projekte."""
        if not self.is_configured:
            print("E-Mail-Service ist nicht konfiguriert. Keine E-Mail gesendet.")
            return False
        
        if not new_projects:
            print("Keine neuen Projekte gefunden. Keine E-Mail gesendet.")
            return False
        
        if scan_time is None:
            scan_time = datetime.now()
        
        # E-Mail erstellen
        message = emails.html(
            html=JinjaTemplate(filename=self.new_projects_template),
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
        response = message.send(
            to=recipient,
            render=context,
            smtp={
                "host": self.smtp_host,
                "port": self.smtp_port,
                "user": self.smtp_user,
                "password": self.smtp_password,
                "tls": True
            }
        )
        
        success = response.status_code == 250
        if success:
            print(f"E-Mail erfolgreich an {recipient} gesendet.")
        else:
            print(f"Fehler beim Senden der E-Mail: {response.status_code}")
        
        return success
    
    def get_config_status(self) -> Dict:
        """Gibt den Status der E-Mail-Konfiguration zurück."""
        return {
            "is_configured": self.is_configured,
            "smtp_host": self.smtp_host,
            "smtp_port": self.smtp_port,
            "smtp_user": self.smtp_user,
            "sender": self.sender,
            "frontend_url": self.frontend_url
        }
