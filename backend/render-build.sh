#!/bin/bash
# Render.com build script für das Backend

set -e  # Exit on error
set -x  # Print commands for debugging

echo "Starting build process..."
echo "Environment: RENDER=$RENDER"
echo "Python version: $(python --version)"
echo "Pip version: $(pip --version)"

# Upgrade pip to latest version
echo "Upgrading pip..."
pip install --upgrade pip

# Install Python dependencies (without Playwright)
echo "Installing Python dependencies..."
pip install -r requirements.txt

echo "✅ Build completed successfully!"
echo "Installed packages:"
pip list

# Verzeichnisse erstellen
echo "Creating data directories..."
mkdir -p data/debug

echo "Build completed successfully!"
