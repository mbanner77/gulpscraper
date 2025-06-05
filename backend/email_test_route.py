"""
E-Mail-Test-Route für GULP Job Scraper
=====================================
Diese Route ermöglicht das Testen der E-Mail-Konfiguration.
"""

from fastapi import APIRouter, HTTPException, Body
import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr

router = APIRouter()

# Referenzen auf globale Variablen aus scraper.py
email_service = None
email_recipient = None
DEFAULT_EMAIL_RECIPIENT = None

def initialize(email_svc, email_rcpt, default_email_rcpt):
    """Initialisiert die globalen Variablen für die E-Mail-Test-Route."""
    global email_service, email_recipient, DEFAULT_EMAIL_RECIPIENT
    email_service = email_svc
    email_recipient = email_rcpt
    DEFAULT_EMAIL_RECIPIENT = default_email_rcpt


@router.get("/config")
async def get_email_config():
    """Gibt die aktuelle E-Mail-Konfiguration zurück."""
    if not email_service:
        return {
            "is_configured": False,
            "message": "E-Mail-Service ist nicht initialisiert."
        }
    
    config = email_service.get_config_status()
    # Passwort aus Sicherheitsgründen nicht zurückgeben
    if "smtp_password" in config:
        config["smtp_password"] = "********"
    
    config["enabled"] = True  # Wir verwenden jetzt immer die Standard-Konfiguration
    config["recipient"] = email_recipient or DEFAULT_EMAIL_RECIPIENT
    
    return config


class EmailTestRequest(BaseModel):
    email: Optional[EmailStr] = None

@router.post("/test")
async def test_email(request: EmailTestRequest = Body(default=None)):
    """Testet die E-Mail-Konfiguration durch Senden einer Test-E-Mail."""
    global email_service
    
    # Extrahiere die E-Mail-Adresse aus der Anfrage oder verwende die Standard-Adresse
    test_recipient = None
    if request and hasattr(request, 'email') and request.email:
        test_recipient = request.email
    
    test_recipient = test_recipient or email_recipient or DEFAULT_EMAIL_RECIPIENT
    
    if not test_recipient:
        return {
            "success": False,
            "message": "Keine E-Mail-Adresse angegeben."
        }
    
    if not email_service or not email_service.is_configured:
        return {
            "success": False,
            "message": "E-Mail-Service ist nicht konfiguriert."
        }
    
    # Erstelle ein Test-Projekt
    test_project = {
        "id": "test-123",
        "title": "Test-Projekt",
        "description": "Dies ist ein Test-Projekt, um die E-Mail-Konfiguration zu testen.",
        "companyName": "Test GmbH",
        "location": "Berlin",
        "originalPublicationDate": datetime.datetime.now().isoformat(),
        "url": "https://www.gulp.de/"
    }
    
    try:
        success = email_service.send_new_projects_notification(
            recipient=test_recipient,
            new_projects=[test_project],
            scan_time=datetime.datetime.now()
        )
        
        if success:
            return {
                "success": True,
                "message": f"Test-E-Mail erfolgreich an {test_recipient} gesendet."
            }
        else:
            return {
                "success": False,
                "message": "Fehler beim Senden der Test-E-Mail."
            }
    except Exception as e:
        return {
            "success": False,
            "message": f"Fehler beim Senden der Test-E-Mail: {str(e)}"
        }
