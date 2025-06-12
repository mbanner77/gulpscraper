"""
E-Mail-Test-Route für GULP Job Scraper
=====================================
Diese Route ermöglicht das Testen der E-Mail-Konfiguration.
"""

from fastapi import APIRouter, HTTPException, Body
import datetime
import os
import socket
import traceback
from typing import Optional, Dict, Any
from pydantic import BaseModel, EmailStr

router = APIRouter()

# Referenzen auf globale Variablen aus scraper.py
email_service = None
email_recipient = None
DEFAULT_EMAIL_RECIPIENT = None

def initialize(email_svc, email_rcpt, default_email_rcpt=None):
    """Initialisiert die globalen Variablen für die E-Mail-Test-Route."""
    global email_service, email_recipient, DEFAULT_EMAIL_RECIPIENT
    email_service = email_svc
    email_recipient = email_rcpt
    DEFAULT_EMAIL_RECIPIENT = default_email_rcpt
    
    print(f"[EMAIL_TEST] E-Mail-Test-Route initialisiert")
    print(f"[EMAIL_TEST] E-Mail-Service: {email_service is not None}")
    print(f"[EMAIL_TEST] E-Mail-Empfänger: {email_recipient}")


@router.get("/config")
async def get_email_config():
    """Gibt die aktuelle E-Mail-Konfiguration zurück."""
    result = {
        "is_configured": False,
        "environment": "render" if os.environ.get('RENDER') else "local",
        "hostname": socket.gethostname(),
        "smtp_env_vars": {
            "SMTP_HOST": os.environ.get("SMTP_HOST", "nicht gesetzt"),
            "SMTP_PORT": os.environ.get("SMTP_PORT", "nicht gesetzt"),
            "SMTP_USER": os.environ.get("SMTP_USER", "nicht gesetzt"),
            "SMTP_PASSWORD": "********" if os.environ.get("SMTP_PASSWORD") else "nicht gesetzt",
            "EMAIL_SENDER": os.environ.get("EMAIL_SENDER", "nicht gesetzt")
        }
    }
    
    if not email_service:
        result["message"] = "E-Mail-Service ist nicht initialisiert."
        return result
    
    config = email_service.get_config_status()
    # Passwort aus Sicherheitsgründen nicht zurückgeben
    if "smtp_password" in config:
        config["smtp_password"] = "********"
    
    config["enabled"] = True  # Wir verwenden jetzt immer die Standard-Konfiguration
    config["recipient"] = email_recipient or DEFAULT_EMAIL_RECIPIENT
    
    # Kombiniere die Ergebnisse
    result.update(config)
    
    return result


class EmailTestRequest(BaseModel):
    email: Optional[EmailStr] = None

@router.post("/test")
async def test_email(request: EmailTestRequest = Body(default=None)):
    """Testet die E-Mail-Konfiguration durch Senden einer Test-E-Mail."""
    global email_service
    
    print("\n[EMAIL_TEST] Starte E-Mail-Test...")
    
    # Extrahiere die E-Mail-Adresse aus der Anfrage oder verwende die Standard-Adresse
    test_recipient = None
    if request and hasattr(request, 'email') and request.email:
        test_recipient = request.email
    
    test_recipient = test_recipient or email_recipient or DEFAULT_EMAIL_RECIPIENT
    
    print(f"[EMAIL_TEST] Test-Empfänger: {test_recipient}")
    
    if not test_recipient:
        print("[EMAIL_TEST] Keine E-Mail-Adresse angegeben.")
        return {
            "success": False,
            "message": "Keine E-Mail-Adresse angegeben."
        }
    
    if not email_service:
        print("[EMAIL_TEST] E-Mail-Service ist nicht initialisiert.")
        return {
            "success": False,
            "message": "E-Mail-Service ist nicht initialisiert."
        }
    
    if not email_service.is_configured:
        print("[EMAIL_TEST] E-Mail-Service ist nicht konfiguriert.")
        config_status = email_service.get_config_status() if email_service else {}
        return {
            "success": False,
            "message": "E-Mail-Service ist nicht konfiguriert.",
            "config": config_status
        }
    
    # Erstelle ein Test-Projekt
    test_project = {
        "id": "test-123",
        "title": "Test-Projekt",
        "description": "Dies ist ein Test-Projekt, um die E-Mail-Konfiguration zu testen.",
        "companyName": "Test GmbH",
        "location": "Berlin",
        "isRemoteWorkPossible": True,
        "publicationDate": datetime.datetime.now().strftime("%d.%m.%Y"),
        "originalPublicationDate": datetime.datetime.now().isoformat(),
        "url": "https://www.gulp.de/"
    }
    
    print(f"[EMAIL_TEST] Sende Test-E-Mail mit Konfiguration: {email_service.get_config_status()}")
    
    try:
        success = email_service.send_new_projects_notification(
            recipient=test_recipient,
            new_projects=[test_project],
            scan_time=datetime.datetime.now()
        )
        
        if success:
            print(f"[EMAIL_TEST] Test-E-Mail erfolgreich an {test_recipient} gesendet.")
            return {
                "success": True,
                "message": f"Test-E-Mail erfolgreich an {test_recipient} gesendet.",
                "config": email_service.get_config_status() if email_service else {}
            }
        else:
            print(f"[EMAIL_TEST] Fehler beim Senden der Test-E-Mail.")
            return {
                "success": False,
                "message": "Fehler beim Senden der Test-E-Mail.",
                "config": email_service.get_config_status() if email_service else {}
            }
    except Exception as e:
        print(f"[EMAIL_TEST] Exception beim Senden der Test-E-Mail: {str(e)}")
        print(f"[EMAIL_TEST] Traceback: {traceback.format_exc()}")
        return {
            "success": False,
            "message": f"Fehler beim Senden der Test-E-Mail: {str(e)}",
            "error_details": traceback.format_exc(),
            "config": email_service.get_config_status() if email_service else {}
        }


@router.get("/diagnose")
async def diagnose_email_service():
    """Diagnoseinformationen für den E-Mail-Service."""
    result: Dict[str, Any] = {
        "timestamp": datetime.datetime.now().isoformat(),
        "hostname": socket.gethostname(),
        "environment": "render" if os.environ.get('RENDER') else "local",
        "email_service_initialized": email_service is not None,
        "environment_variables": {}
    }
    
    # Umgebungsvariablen sammeln (ohne sensible Daten)
    for key, value in os.environ.items():
        if key.startswith("SMTP_") or key.startswith("EMAIL_"):
            if "PASSWORD" in key or "SECRET" in key:
                result["environment_variables"][key] = "********"
            else:
                result["environment_variables"][key] = value
    
    # Netzwerkinformationen
    try:
        result["network"] = {
            "hostname": socket.gethostname(),
            "fqdn": socket.getfqdn(),
            "ip": socket.gethostbyname(socket.gethostname())
        }
    except Exception as e:
        result["network"] = {"error": str(e)}
    
    # E-Mail-Service-Konfiguration
    if email_service:
        try:
            config = email_service.get_config_status()
            if "smtp_password" in config:
                config["smtp_password"] = "********"
            result["email_service_config"] = config
        except Exception as e:
            result["email_service_config"] = {"error": str(e)}
    
    # SMTP-Verbindungstest
    if email_service and email_service.is_configured:
        try:
            import smtplib
            smtp_host = email_service.smtp_host
            smtp_port = email_service.smtp_port
            
            result["smtp_test"] = {"host": smtp_host, "port": smtp_port}
            
            try:
                print(f"[EMAIL_TEST] Teste SMTP-Verbindung zu {smtp_host}:{smtp_port}...")
                smtp = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
                result["smtp_test"]["connection"] = "success"
                
                try:
                    smtp.ehlo()
                    result["smtp_test"]["ehlo"] = "success"
                    
                    if smtp_port == 587:
                        try:
                            smtp.starttls()
                            result["smtp_test"]["starttls"] = "success"
                        except Exception as e:
                            result["smtp_test"]["starttls"] = {"error": str(e)}
                    
                    smtp.quit()
                except Exception as e:
                    result["smtp_test"]["ehlo"] = {"error": str(e)}
            except Exception as e:
                result["smtp_test"]["connection"] = {"error": str(e)}
        except Exception as e:
            result["smtp_test"] = {"error": str(e)}
    
    return result
