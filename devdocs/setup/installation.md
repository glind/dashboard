# Installation Guide

## Prerequisites
- Python 3.8+
- Git
- Internet connection for API integrations

## Quick Installation
```bash
git clone <repo-url>
cd dashboard
./startup.sh
```

The startup script will:
- Create virtual environment
- Install all dependencies
- Initialize database
- Start the server

## Manual Setup (if needed)
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config/config.yaml.example config/config.yaml
cp config/credentials.yaml.example config/credentials.yaml
python3 simple_main.py
```

## Dependencies
- **FastAPI** - Web framework
- **Uvicorn** - ASGI server
- **Aiohttp** - HTTP client
- **BeautifulSoup4** - Web scraping
- **Feedparser** - RSS feeds
- **Google API client libraries** - Gmail/Calendar
- **PyYAML** - Configuration files

## Configuration
1. **Google APIs**: Set up OAuth in Google Cloud Console
2. **GitHub**: Create personal access token
3. **TickTick**: OAuth credentials (optional)
4. **Weather**: API key for weather service

See `api/authentication.md` for detailed setup.
