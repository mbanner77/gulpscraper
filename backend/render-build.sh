#!/bin/bash
# Render.com build script für das Backend

set -e  # Exit on error
set -x  # Print commands for debugging

echo "Starting build process..."

# System dependencies for Playwright
echo "Installing system dependencies for Playwright..."
apt-get update || true
apt-get install -y libglib2.0-0 libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libdbus-1-3 libxcb1 libxkbcommon0 libx11-6 libxcomposite1 libxdamage1 libxext6 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2 libatspi2.0-0 || true

# Python-Abhängigkeiten installieren
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Playwright installieren und Browser herunterladen
echo "Installing Playwright..."
pip install playwright==1.40.0

echo "Installing Playwright browsers..."
python -m playwright install chromium

# Verify installation
echo "Verifying Playwright installation..."
ls -la /opt/render/.cache/ms-playwright/ || echo "ms-playwright directory not found"
ls -la /opt/render/.cache/ms-playwright/chromium-*/ || echo "No chromium directory found"
ls -la /opt/render/.cache/ms-playwright/chromium-*/chrome-linux/ || echo "No chrome-linux directory found"

# Verzeichnisse erstellen
echo "Creating data directories..."
mkdir -p data/debug

echo "Build completed successfully!"
