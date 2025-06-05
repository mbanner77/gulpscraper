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

**Scraping-Funktionen:**
- Automatisches Scraping von GULP-Projektdaten mit Playwright
- Automatische Erkennung neuer Projekte
- Manuelles Auslösen des Scrapings über API-Endpunkt

**Scheduler-Funktionen:**
- Konfigurierbarer Scheduler für automatische Scans
- Mehrere tägliche Scan-Zeiten einstellbar (Standard: 3 Uhr morgens)
- Robuste Scheduler-Implementierung mit Selbstheilungsfunktionen
- API-Endpunkt zum Neustarten des Schedulers bei Problemen

**Datenmanagement:**
- REST API zum Zugriff auf die gescrapten Daten
- Filterung und Paginierung der Projektdaten
- Projekt-Archivierung (Projekte älter als 24 Stunden)
- Filterung nach Standort und Remote-Status

**Benachrichtigungen:**
- E-Mail-Benachrichtigungen bei neuen Projekten
- Konfigurierbare E-Mail-Einstellungen

### Frontend

**Benutzeroberfläche:**
- Moderne Benutzeroberfläche mit Material-UI
- Responsive Design für Desktop und Mobile
- Tab-basierte Navigation mit URL-Persistenz

**Projektansicht:**
- Projektliste mit Paginierung
- Suche und Filterung nach Titel, Beschreibung, Firma, Standort und Remote-Möglichkeit
- Detailansicht für jedes Projekt
- Favoritenfunktion mit lokaler Speicherung
- Separate Ansicht für aktuelle Projekte (letzte 24 Stunden) und Archiv

**Scheduler-Konfiguration:**
- Benutzerfreundliche Oberfläche zur Konfiguration des Schedulers
- Hinzufügen/Entfernen mehrerer täglicher Scan-Zeiten
- Kartenbasierte Darstellung der konfigurierten Scan-Zeiten
- Ein/Aus-Schalter für den Scheduler

**Scraper-Steuerung:**
- Manuelles Auslösen des Scrapings
- Statusanzeige für laufende Scraping-Prozesse
- Anzeige des letzten Scan-Zeitpunkts

## Deployment

### Deployment auf Render.com

Dieses Projekt ist für ein einfaches Deployment auf Render.com vorbereitet:

1. Erstellen Sie ein Konto auf [Render.com](https://render.com) (falls noch nicht vorhanden)
2. Klicken Sie auf "New" und wählen Sie "Blueprint"
3. Verbinden Sie Ihr GitHub-Repository
4. Render wird automatisch die `render.yaml`-Datei erkennen und beide Services (Frontend und Backend) einrichten

#### Umgebungsvariablen für Render.com

Folgende Umgebungsvariablen können im Render Dashboard konfiguriert werden:

**Backend:**
- `DATA_DIR`: Verzeichnis für Datenspeicherung (Standard: `data`)
- `EMAIL_RECIPIENT`: E-Mail-Adresse für Benachrichtigungen
- `FRONTEND_URL`: URL des Frontend-Services (wird automatisch von Render gesetzt)
- `RENDER`: Wird automatisch auf `true` gesetzt

**Frontend:**
- `REACT_APP_API_URL`: URL des Backend-Services (wird automatisch von Render gesetzt)
- `REACT_APP_HUGGINGFACE_API_KEY`: Optional für KI-Funktionen

### Mit Docker Compose (lokale Entwicklung)

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
   - Name: `gulp-backend` (wichtig: verwenden Sie ein konsistentes Namensschema für Frontend und Backend)
   - Environment: `Docker`
   - Branch: `main` (oder Ihr Hauptbranch)
   - Root Directory: `backend`
   - Instance Type: Wählen Sie "Standard" (mindestens 1 GB RAM wegen Playwright)
   - Disk: Mindestens 1 GB
   - Environment Variables: Fügen Sie folgende Variablen hinzu:
     - `FRONTEND_URL`: Die URL Ihres Frontend-Services (z.B. `https://gulp-frontend.onrender.com`)
4. Klicken Sie auf "Create Web Service"

### 3. Frontend-Deployment (Static Site)

1. Gehen Sie zu Ihrem Render Dashboard und klicken Sie auf "New" > "Static Site"
2. Verbinden Sie dasselbe Repository
3. Konfigurieren Sie den Dienst:
   - Name: `gulp-frontend` (wichtig: verwenden Sie ein Namensschema wie "gulp-frontend" für das Frontend und "gulp-backend" für das Backend)
   - Branch: `main` (oder Ihr Hauptbranch)
   - Root Directory: `frontend`
   - Build Command: `npm ci && npm run build`
   - Publish Directory: `build`
   - Environment Variables: Fügen Sie `REACT_APP_API_URL=https://gulp-backend.onrender.com` hinzu (ersetzen Sie "gulp-backend" mit dem tatsächlichen Namen Ihres Backend-Services)
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

### 6. Fehlerbehebung: CORS-Probleme nach Deployment

Wenn nach dem Deployment auf Render.com die Fehlermeldung "Fehler beim Laden der Projekte" erscheint, handelt es sich wahrscheinlich um ein CORS-Problem (Cross-Origin Resource Sharing). Folgen Sie diesen Schritten zur Behebung:

1. **Konsistente Namensgebung verwenden**: Stellen Sie sicher, dass Ihre Services konsistent benannt sind (z.B. `gulp-frontend` und `gulp-backend`). Die automatische API-URL-Erkennung im Frontend basiert auf diesem Namensschema.

2. **FRONTEND_URL korrekt setzen**: Überprüfen Sie, dass die Umgebungsvariable `FRONTEND_URL` im Backend-Service korrekt auf die URL Ihres Frontend-Services gesetzt ist.

3. **Browser-Konsole prüfen**: Öffnen Sie die Browser-Konsole (F12), um genauere Fehlermeldungen zu sehen. CORS-Fehler werden dort deutlich angezeigt.

4. **Manuelles Testen der API**: Testen Sie die Backend-API direkt mit einem Tool wie Postman oder curl, um zu überprüfen, ob sie korrekt antwortet:
   ```bash
   curl https://gulp-backend.onrender.com/projects
   ```

5. **Cache leeren**: Leeren Sie den Browser-Cache oder öffnen Sie die Seite im Inkognito-Modus, um sicherzustellen, dass keine alten Konfigurationen verwendet werden.

6. **Deployment-Logs prüfen**: Überprüfen Sie die Logs beider Services in Ihrem Render-Dashboard auf Fehler oder Warnungen.

### 7. Fehlerbehebung: Scheduler läuft nicht nach dem Deployment

Wenn der Scheduler nach dem Deployment nicht korrekt läuft oder keine Jobs ausführt, können Sie folgende Schritte zur Behebung durchführen:

1. **Scheduler-Status überprüfen**: Rufen Sie den Endpunkt `/scheduler-config` auf, um den aktuellen Status des Schedulers zu sehen:
   ```bash
   curl https://gulp-backend.onrender.com/scheduler-config
   ```
   Die Antwort sollte `"scheduler_running": true` und mindestens einen Job in der `jobs`-Liste enthalten.

2. **Scheduler neu starten**: Verwenden Sie den speziellen Endpunkt zum Neustarten des Schedulers:
   ```bash
   curl -X POST https://gulp-backend.onrender.com/restart-scheduler
   ```
   Dies erzwingt einen Neustart des Schedulers und konfiguriert die Jobs neu.

3. **Logs auf Fehler prüfen**: Überprüfen Sie die Backend-Logs im Render-Dashboard auf Fehler im Zusammenhang mit dem Scheduler oder datetime-Modulen.

4. **Zeitzone beachten**: Der Scheduler verwendet die Systemzeit des Servers. Render-Server verwenden UTC, daher wird ein Job, der für 3:00 Uhr konfiguriert ist, um 3:00 Uhr UTC ausgeführt (was je nach Ihrer Zeitzone zu einer anderen lokalen Zeit führt).

5. **Manuellen Scrape auslösen**: Testen Sie, ob der Scraper grundsätzlich funktioniert, indem Sie einen manuellen Scrape auslösen:
   ```bash
   curl -X POST https://gulp-backend.onrender.com/scrape
   ```

6. **Service neu starten**: Als letztes Mittel können Sie den gesamten Backend-Service in Render neu starten, um sicherzustellen, dass der Scheduler korrekt initialisiert wird.

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
