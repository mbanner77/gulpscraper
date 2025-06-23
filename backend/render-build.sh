#!/bin/bash
#!/bin/bash
# Render.com build script für das Backend

set -e  # Exit on error
set -x  # Print commands for debugging

echo "Starting build process..."

# Python-Abhängigkeiten installieren
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Playwright installieren und Browser herunterladen
echo "Installing Playwright..."
pip install playwright==1.40.0

echo "Installing Playwright browsers..."
python -m playwright install chromium --with-deps

# Verify installation
echo "Verifying Playwright installation..."
ls -la /opt/render/.cache/ms-playwright/
ls -la /opt/render/.cache/ms-playwright/chromium-*/ || echo "No chromium directory found"
ls -la /opt/render/.cache/ms-playwright/chromium-*/chrome-linux/ || echo "No chrome-linux directory found"

# Verzeichnisse erstellen
echo "Creating data directories..."
mkdir -p data/debug

echo "Build completed successfully!"
