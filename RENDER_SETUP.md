# Render Deployment Setup

## Umgebungsvariablen für Render

### Backend Service (Python)

Setzen Sie diese Umgebungsvariablen in Ihrem Render Backend Service:

#### E-Mail-Konfiguration (für Benachrichtigungen)
```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=ihr-email@gmail.com
SMTP_PASSWORD=ihr-app-passwort
EMAIL_SENDER=GULP Job Scraper <ihr-email@gmail.com>
```

#### Anwendungs-Konfiguration
```
RENDER=true
CLOUD_ENV=true
PYTHONPATH=./backend
DATA_DIR=./data
```

#### Frontend URL (wird automatisch von render.yaml gesetzt)
```
FRONTEND_URL=https://ihr-frontend-service.onrender.com
```

### Frontend Service (Static Site)

Wird automatisch über render.yaml konfiguriert:
```
REACT_APP_API_URL=https://ihr-backend-service.onrender.com
```

## Fehlerbehebung

### 1. Document Service Fehler

**Problem:** "Document service connection failed: The string did not match the expected pattern"

**Lösung:**
- Überprüfen Sie, dass das Backend-Service läuft
- Kontrollieren Sie die Logs des Backend-Services auf Fehler
- Stellen Sie sicher, dass die Document-Routes richtig importiert werden

**Debug-Schritte:**
1. Besuchen Sie `https://ihr-backend-service.onrender.com/documents/health`
2. Überprüfen Sie die Backend-Logs auf Document-Analyzer Initialisierung
3. Prüfen Sie, ob alle Python-Dependencies installiert sind

### 2. E-Mail-Versand funktioniert nicht

**Problem:** E-Mails werden nicht gesendet

**Lösung:**
1. **Gmail App-Passwort erstellen:**
   - Gehen Sie zu [Google Account Security](https://myaccount.google.com/security)
   - Aktivieren Sie 2-Faktor-Authentifizierung
   - Erstellen Sie ein App-Passwort für "Mail"
   - Verwenden Sie dieses Passwort als `SMTP_PASSWORD`

2. **Umgebungsvariablen setzen:**
   ```
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=ihre-gmail-adresse@gmail.com
   SMTP_PASSWORD=ihr-16-stelliges-app-passwort
   EMAIL_SENDER=GULP Job Scraper <ihre-gmail-adresse@gmail.com>
   ```

3. **Alternative SMTP-Provider:**
   - **SendGrid:** Kostenloses Kontingent verfügbar
   - **Mailgun:** Kostenloses Kontingent verfügbar
   - **Amazon SES:** Pay-per-use

### Deployment-Probleme

**Build-Fehler:**
- Überprüfen Sie die Build-Logs in Render
- Stellen Sie sicher, dass `render-build.sh` ausführbar ist
- Kontrollieren Sie, dass alle Dependencies in `requirements.txt` aufgelistet sind

**Runtime-Fehler:**
- Überprüfen Sie die Service-Logs
- Stellen Sie sicher, dass alle Umgebungsvariablen gesetzt sind
- Prüfen Sie, ob der Gunicorn-Server richtig startet

## Render Services

Ihre Anwendung besteht aus zwei Services:

1. **Backend (Python/FastAPI):**
   - Service-Typ: Web Service
   - Build-Befehl: `cd backend && ./render-build.sh`
   - Start-Befehl: `cd backend && gunicorn -w 4 -k uvicorn.workers.UvicornWorker scraper:app`

2. **Frontend (React):**
   - Service-Typ: Static Site
   - Build-Befehl: `cd frontend && npm install && npm run build`
   - Publish-Verzeichnis: `./frontend/build`

## Monitoring

- **Health Checks:** `https://ihr-backend-service.onrender.com/health`
- **Document Health:** `https://ihr-backend-service.onrender.com/documents/health`
- **Service Logs:** Über das Render-Dashboard verfügbar

## Typische Fehlerquellen

1. **Falsche API-URLs:** Frontend kann Backend nicht erreichen
2. **Fehlende Umgebungsvariablen:** Services starten nicht richtig
3. **Build-Fehler:** Dependencies nicht installiert
4. **CORS-Fehler:** Frontend und Backend auf verschiedenen Domains
5. **E-Mail-Konfiguration:** SMTP-Credentials falsch oder fehlend

---

## ✅ Recent Improvements (Latest Version)

### 1. **Fixed Build Issues**
- **Pydantic**: Updated to version 2.6.4 with pre-compiled wheels (no more Rust compilation errors)
- **Dependencies**: All updated to versions compatible with Render's Python environment
- **Build Script**: Simplified `render-build.sh` to avoid Playwright installation issues
- **Requirements**: Split into `requirements.txt` (production) and `requirements_dev.txt` (local development)

### 2. **Cloud-Compatible Scraping**
- **Cloud Scraper**: New `cloud_scraper.py` module using `requests` instead of Playwright
- **Automatic Detection**: Backend automatically uses cloud scraper in Render environment
- **API Integration**: Direct integration with GULP's REST API for reliable cloud scraping
- **Lightweight**: No browser dependencies, faster deployment and startup

### 3. **Enhanced Error Handling**
- **Document Service**: Improved initialization and health checks
- **Email Service**: Better SMTP configuration validation
- **Archive Support**: Projects can now be loaded from archive data
- **Comprehensive Logging**: Better debugging with correlation IDs

### 4. **Deployment Stability**
- **No Rust Compilation**: All dependencies use pre-compiled wheels
- **Faster Builds**: Simplified build process without browser installation
- **Better Error Messages**: Clear indication of what's wrong and how to fix it
- **Health Monitoring**: Multiple endpoints for service health checks

### 5. **Development Experience**
- **Local Setup**: `LOCAL_DEVELOPMENT.md` with complete setup instructions
- **Dual Mode**: Full Playwright functionality locally, lightweight cloud scraping on Render
- **Testing Tools**: `test_endpoints.py` for API validation
- **Clear Documentation**: Separate guides for local development vs cloud deployment
