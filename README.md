# GULP Job App

Eine kombinierte Anwendung zum Scrapen und Anzeigen von GULP.de Freelance-Projekten. Diese Anwendung besteht aus:

1. Einem Python-Backend mit Playwright zum Scrapen von GULP-Projektdaten
2. Einem React-Frontend zur Anzeige und Verwaltung der Projektdaten

## Projektstruktur

```
gulp-job-app/
├── backend/                # Python Scraper & API
│   ├── scraper.py          # Hauptskript für Scraping und API
│   ├── requirements.txt    # Python-Abhängigkeiten
│   └── Dockerfile          # Docker-Konfiguration für das Backend
├── frontend/               # React-Frontend
│   ├── src/                # React-Quellcode
│   ├── public/             # Statische Dateien
│   ├── package.json        # NPM-Abhängigkeiten
│   ├── Dockerfile          # Docker-Konfiguration für das Frontend
│   └── nginx.conf          # NGINX-Konfiguration für das Frontend
├── docker-compose.yml      # Docker Compose für lokale Entwicklung
└── README.md               # Projektdokumentation
```

## Funktionen

### Backend

- Automatisches Scraping von GULP-Projektdaten mit Playwright
- REST API zum Zugriff auf die gescrapten Daten
- Filterung und Paginierung der Projektdaten
- Geplantes tägliches Scraping (3 Uhr morgens)
- Manuelles Auslösen des Scrapings über API-Endpunkt

### Frontend

- Moderne Benutzeroberfläche mit Material-UI
- Projektliste mit Paginierung
- Suche und Filterung nach Titel, Beschreibung, Firma, Standort und Remote-Möglichkeit
- Detailansicht für jedes Projekt
- Favoritenfunktion mit lokaler Speicherung
- Scraper-Steuerung zum manuellen Auslösen des Scrapings

## Lokale Entwicklung

### Mit Docker Compose

1. Stellen Sie sicher, dass Docker und Docker Compose installiert sind
2. Klonen Sie das Repository
3. Starten Sie die Anwendung mit Docker Compose:

```bash
docker-compose up -d
```

Die Anwendung ist dann unter http://localhost verfügbar.

### Ohne Docker

#### Backend

1. Navigieren Sie zum Backend-Verzeichnis:

```bash
cd backend
```

2. Erstellen Sie eine virtuelle Umgebung und installieren Sie die Abhängigkeiten:

```bash
python -m venv venv
source venv/bin/activate  # Unter Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

3. Starten Sie das Backend:

```bash
uvicorn scraper:app --host 0.0.0.0 --port 8000
```

#### Frontend

1. Navigieren Sie zum Frontend-Verzeichnis:

```bash
cd frontend
```

2. Installieren Sie die Abhängigkeiten:

```bash
npm install
```

3. Starten Sie das Frontend:

```bash
npm start
```

## Deployment auf Render.com

Diese Anwendung kann einfach auf Render.com bereitgestellt werden. Hier ist eine Schritt-für-Schritt-Anleitung:

### 1. Konto erstellen

Falls Sie noch kein Konto haben, erstellen Sie eines auf [Render.com](https://render.com).

### 2. Backend-Deployment (Web Service)

1. Gehen Sie zu Ihrem Render Dashboard und klicken Sie auf "New" > "Web Service"
2. Verbinden Sie Ihr GitHub-Repository oder laden Sie den Code direkt hoch
3. Konfigurieren Sie den Dienst:
   - Name: `gulp-scraper-api`
   - Environment: `Docker`
   - Branch: `main` (oder Ihr Hauptbranch)
   - Root Directory: `backend`
   - Instance Type: Wählen Sie "Standard" (mindestens 1 GB RAM wegen Playwright)
   - Disk: Mindestens 1 GB
4. Klicken Sie auf "Create Web Service"

### 3. Frontend-Deployment (Static Site)

1. Gehen Sie zu Ihrem Render Dashboard und klicken Sie auf "New" > "Static Site"
2. Verbinden Sie dasselbe Repository
3. Konfigurieren Sie den Dienst:
   - Name: `gulp-job-viewer`
   - Branch: `main` (oder Ihr Hauptbranch)
   - Root Directory: `frontend`
   - Build Command: `npm ci && npm run build`
   - Publish Directory: `build`
   - Environment Variables: Fügen Sie `REACT_APP_API_URL=https://ihre-backend-url.onrender.com` hinzu (ersetzen Sie die URL mit Ihrer tatsächlichen Backend-URL)
4. Klicken Sie auf "Create Static Site"

### 4. Umgebungsvariablen konfigurieren

Für das Backend müssen Sie möglicherweise zusätzliche Umgebungsvariablen in den Render-Einstellungen konfigurieren:

- `PORT`: 8000
- `NODE_ENV`: production

### 5. Persistenter Speicher (Disk)

Da der Scraper Daten speichern muss, sollten Sie einen persistenten Speicher für das Backend konfigurieren:

1. Gehen Sie zu Ihren Backend-Service-Einstellungen
2. Scrollen Sie nach unten zu "Disks"
3. Klicken Sie auf "Add Disk"
4. Konfigurieren Sie:
   - Name: `gulp-data`
   - Mount Path: `/app/data`
   - Size: 1 GB (oder mehr, je nach Bedarf)

## API-Endpunkte

- `GET /projects` - Liste aller Projekte mit Filterung und Paginierung
  - Query-Parameter: `search`, `location`, `remote`, `page`, `limit`
- `GET /projects/{id}` - Details zu einem bestimmten Projekt
- `POST /scrape` - Manuelles Auslösen des Scrapings
  - Body: `{ "pages": [1, 2, 3] }` (optional)
- `GET /status` - Status des Scrapers abrufen

## Technologien

- **Backend**: Python, FastAPI, Playwright, APScheduler
- **Frontend**: React, Material-UI, Axios
- **Deployment**: Docker, NGINX, Render.com

## Hinweise

- Der Scraper läuft standardmäßig einmal täglich um 3 Uhr morgens
- Die Daten werden im persistenten Speicher auf Render.com gespeichert
- Die Anwendung ist so konfiguriert, dass sie automatisch neu startet, wenn sie abstürzt
