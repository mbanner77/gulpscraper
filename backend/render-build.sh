#!/bin/bash
# Render.com build script für das Backend

# Python-Abhängigkeiten installieren
pip install -r requirements.txt

# Playwright installieren und Browser herunterladen
pip install playwright
playwright install chromium

# Verzeichnisse erstellen
mkdir -p data/debug

echo "Build abgeschlossen!"
