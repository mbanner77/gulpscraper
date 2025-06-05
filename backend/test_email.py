#!/usr/bin/env python3
"""
Test-Skript für den E-Mail-Versand
==================================
Dieses Skript testet die E-Mail-Konfiguration und sendet eine Test-E-Mail.
"""

import os
import sys
import datetime
from email_service import EmailService

# Standard SMTP-Konfiguration
SMTP_HOST = "mail.tk-core.de"
SMTP_PORT = 465
SMTP_USER = "gulpai@tk-core.de"
SMTP_PASSWORD = "gulpai2025"
EMAIL_SENDER = "GULP Job Scraper <gulpai@tk-core.de>"
EMAIL_RECIPIENT = "m.banner@realcore.de"
FRONTEND_URL = "http://localhost:3000"

def test_email_service():
    """Testet den E-Mail-Service mit den Standard-Einstellungen."""
    print(f"Teste E-Mail-Versand mit folgender Konfiguration:")
    print(f"SMTP-Server: {SMTP_HOST}:{SMTP_PORT}")
    print(f"Benutzer: {SMTP_USER}")
    print(f"Absender: {EMAIL_SENDER}")
    print(f"Empfänger: {EMAIL_RECIPIENT}")
    
    # E-Mail-Service initialisieren
    email_service = EmailService(
        smtp_host=SMTP_HOST,
        smtp_port=SMTP_PORT,
        smtp_user=SMTP_USER,
        smtp_password=SMTP_PASSWORD,
        sender=EMAIL_SENDER,
        frontend_url=FRONTEND_URL
    )
    
    if not email_service.is_configured:
        print("E-Mail-Service ist nicht konfiguriert!")
        return False
    
    # Test-Projekt erstellen
    test_project = {
        "id": "test-123",
        "title": "Test-Projekt",
        "description": "Dies ist ein Test-Projekt, um die E-Mail-Konfiguration zu testen.",
        "companyName": "Test GmbH",
        "location": "Berlin",
        "originalPublicationDate": datetime.datetime.now().isoformat(),
        "url": "https://www.gulp.de/"
    }
    
    # Test-E-Mail senden
    success = email_service.send_new_projects_notification(
        recipient=EMAIL_RECIPIENT,
        new_projects=[test_project],
        scan_time=datetime.datetime.now()
    )
    
    if success:
        print(f"Test-E-Mail erfolgreich an {EMAIL_RECIPIENT} gesendet!")
    else:
        print("Fehler beim Senden der Test-E-Mail!")
    
    return success

if __name__ == "__main__":
    success = test_email_service()
    sys.exit(0 if success else 1)
