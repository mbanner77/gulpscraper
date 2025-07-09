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
        import sys
        
        # Enhanced environment detection for Render
        is_render = os.environ.get('RENDER', False) or os.environ.get('RENDER_SERVICE_NAME', False)
        is_cloud = is_render or os.environ.get('CLOUD_ENV', False)
        
        print(f"[EMAIL_SERVICE] Environment: Render={is_render}, Cloud={is_cloud}")
        sys.stdout.flush()
        
        self.smtp_host = smtp_host or os.environ.get("SMTP_HOST")
        self.smtp_port = smtp_port or int(os.environ.get("SMTP_PORT", 587))
        self.smtp_user = smtp_user or os.environ.get("SMTP_USER")
        self.smtp_password = smtp_password or os.environ.get("SMTP_PASSWORD")
        self.sender = sender or os.environ.get("EMAIL_SENDER", DEFAULT_SENDER)
        
        # Enhanced frontend URL detection for Render
        if frontend_url:
            self.frontend_url = frontend_url
        elif os.environ.get("FRONTEND_URL"):
            self.frontend_url = os.environ.get("FRONTEND_URL")
        elif is_render and os.environ.get("RENDER_EXTERNAL_URL"):
            # For Render, try to use the external URL
            self.frontend_url = os.environ.get("RENDER_EXTERNAL_URL")
        else:
            self.frontend_url = "http://localhost"
        
        print(f"[EMAIL_SERVICE] Configuration loaded:")
        print(f"  SMTP Host: {'✓' if self.smtp_host else '✗'} {self.smtp_host or 'Not set'}")
        print(f"  SMTP Port: {self.smtp_port}")
        print(f"  SMTP User: {'✓' if self.smtp_user else '✗'} {self.smtp_user or 'Not set'}")
        print(f"  SMTP Password: {'✓' if self.smtp_password else '✗'} {'[HIDDEN]' if self.smtp_password else 'Not set'}")
        print(f"  Sender: {self.sender}")
        print(f"  Frontend URL: {self.frontend_url}")
        sys.stdout.flush()
        
        # Prüfen, ob die SMTP-Konfiguration vollständig ist
        self.is_configured = all([
            self.smtp_host,
            self.smtp_port,
            self.smtp_user,
            self.smtp_password
        ])
        
        if not self.is_configured:
            print(f"[EMAIL_SERVICE] WARNING: Email service not fully configured!")
            missing = []
            if not self.smtp_host: missing.append("SMTP_HOST")
            if not self.smtp_port: missing.append("SMTP_PORT")
            if not self.smtp_user: missing.append("SMTP_USER")
            if not self.smtp_password: missing.append("SMTP_PASSWORD")
            print(f"[EMAIL_SERVICE] Missing environment variables: {', '.join(missing)}")
            if is_render:
                print(f"[EMAIL_SERVICE] For Render deployment, set these in your service environment variables.")
            sys.stderr.flush()
        else:
            print(f"[EMAIL_SERVICE] Email service fully configured and ready!")
            sys.stdout.flush()
        
        # E-Mail-Template laden
        self.new_projects_template_path = EMAIL_TEMPLATE_DIR / "new_projects.html"
        try:
            if not self.new_projects_template_path.exists():
                print(f"E-Mail-Template nicht gefunden: {self.new_projects_template_path}")
                print(f"Aktuelles Verzeichnis: {Path.cwd()}")
                print(f"Template-Verzeichnis existiert: {EMAIL_TEMPLATE_DIR.exists()}")
                print(f"Inhalt des Template-Verzeichnisses: {list(EMAIL_TEMPLATE_DIR.glob('*')) if EMAIL_TEMPLATE_DIR.exists() else 'Verzeichnis nicht gefunden'}")
                raise FileNotFoundError(f"Template nicht gefunden: {self.new_projects_template_path}")
                
            with open(self.new_projects_template_path, 'r', encoding='utf-8') as f:
                self.new_projects_template = f.read()
                print(f"E-Mail-Template erfolgreich geladen: {len(self.new_projects_template)} Zeichen")
        except Exception as e:
            import traceback
            print(f"Fehler beim Laden des E-Mail-Templates: {str(e)}")
            print(f"Traceback: {traceback.format_exc()}")
            # Fallback-Template für Notfälle
            self.new_projects_template = """
            <h1>Neue GULP Projekte gefunden</h1>
            <p>Es wurden {{new_projects|length}} neue Projekte gefunden.</p>
            <ul>
            {% for project in new_projects %}
                <li><a href="{{project.url}}">{{project.title}}</a> - {{project.companyName}}</li>
            {% endfor %}
            </ul>
            <p><a href="{{frontend_url}}">Alle Projekte im GULP Scraper ansehen</a></p>
            """
            print("Verwende Fallback-Template für E-Mail-Benachrichtigungen.")

    
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
            # Für andere Ports verwenden wir eine Standardkonfiguration basierend auf dem Port
            use_ssl = self.smtp_port == 465
            use_tls = self.smtp_port == 587
            
            # Fallback für andere Ports
            if not use_ssl and not use_tls:
                print(f"Weder SSL (465) noch TLS (587) Port erkannt. Port: {self.smtp_port}")
                # Für Ports < 500 verwenden wir SSL, sonst TLS als Standardwert
                use_ssl = self.smtp_port < 500
                use_tls = not use_ssl
                print(f"Verwende {'SSL' if use_ssl else 'TLS'} als Fallback für Port {self.smtp_port}")
            
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
