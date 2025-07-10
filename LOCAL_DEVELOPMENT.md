# Local Development Setup

This guide explains how to set up the project for local development, including Playwright for full scraping functionality.

## Prerequisites

- Python 3.9+
- Node.js 16+
- Git

## Backend Setup (Local Development)

### 1. Navigate to Backend Directory
```bash
cd backend
```

### 2. Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Development Dependencies
```bash
# Install all dependencies including Playwright
pip install -r requirements_dev.txt

# Install Playwright browsers
python -m playwright install chromium
```

### 4. Set Environment Variables
Create a `.env` file in the backend directory:
```env
# SMTP Configuration (for email functionality)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
EMAIL_SENDER=your-email@gmail.com

# Development settings
CLOUD_ENV=false
RENDER=false
```

### 5. Start Backend Server
```bash
python scraper.py
```

The backend will be available at `http://localhost:8001`

## Frontend Setup

### 1. Navigate to Frontend Directory
```bash
cd frontend
```

### 2. Install Dependencies
```bash
npm install
```

### 3. Start Development Server
```bash
npm start
```

The frontend will be available at `http://localhost:3000`

## Cloud vs Local Development

### Local Development Features:
- ✅ Full Playwright browser automation
- ✅ Complete GULP scraping functionality
- ✅ Document processing with docx2txt
- ✅ Email sending (with proper SMTP config)
- ✅ All API endpoints functional

### Cloud/Render Features:
- ✅ Lightweight HTTP-based scraping
- ✅ Core FastAPI functionality
- ✅ Email sending (with SMTP config)
- ❌ No Playwright browser automation
- ❌ Limited document processing

## Testing

### Test API Endpoints
```bash
# From project root
python backend/test_endpoints.py
```

### Test Health Checks
- Backend health: `http://localhost:8001/health`
- Document health: `http://localhost:8001/documents/health`

## Development vs Production Dependencies

### Development (`requirements_dev.txt`):
- Includes Playwright for full functionality
- Includes testing frameworks
- Suitable for local development

### Production (`requirements.txt`):
- Lightweight dependencies only
- No Playwright (cloud-incompatible)
- Uses cloud_scraper.py for scraping
- Optimized for Render deployment

## Switching Between Environments

The application automatically detects the environment:
- **Local**: Uses Playwright scraper when available
- **Cloud/Render**: Uses lightweight cloud_scraper.py

## Common Issues

### 1. Playwright Installation
If Playwright fails to install:
```bash
# Ensure you have the latest pip
pip install --upgrade pip

# Try installing separately
pip install playwright==1.42.0
python -m playwright install chromium
```

### 2. Email Not Working
- Use Gmail App Passwords (not your regular password)
- Enable 2-factor authentication
- Set correct SMTP settings in `.env`

### 3. Document Processing Issues
- Ensure `docx2txt` is installed
- Check file permissions in data directory

## Directory Structure
```
gulp-job-app/
├── backend/
│   ├── requirements.txt         # Production dependencies
│   ├── requirements_dev.txt     # Development dependencies
│   ├── scraper.py              # Main backend application
│   ├── cloud_scraper.py        # Cloud-compatible scraper
│   ├── render-build.sh         # Render build script
│   └── ...
├── frontend/
│   ├── package.json
│   ├── src/
│   └── ...
└── data/                       # Data storage directory
```

## Debugging

### Backend Logging
- Logs are written to console and optionally to files
- Set `DEBUG=true` in environment for verbose logging
- Health check endpoints provide service status

### Frontend Debugging  
- Open browser Developer Tools
- Check Network tab for API calls
- Console logs show detailed error information

## Deployment

- **Local**: Use development setup above
- **Render**: Automatically uses production configuration
- **Other Cloud**: May require additional configuration
