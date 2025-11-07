# Setup Guide

## Prerequisites

- **Python 3.10+** (3.11 recommended)
- **Git**
- **Docker** (optional, for containerized deployment)
- Internet connection for API integrations

## Quick Start (Local Development)

```bash
# Clone repository
git clone https://github.com/buildly-marketplace/personal-dashboard.git
cd personal-dashboard

# Run startup script (handles venv, dependencies, database)
./ops/startup.sh
```

The dashboard will be available at `http://localhost:8008`

## Environment Variables

Create a `.env` file in the project root or set these variables:

### Required

```bash
# Google OAuth (for Gmail & Calendar)
GOOGLE_CLIENT_ID=your_client_id_here
GOOGLE_CLIENT_SECRET=your_client_secret_here

# GitHub Personal Access Token
GITHUB_TOKEN=your_github_token_here
```

### Optional Services

```bash
# TickTick (Task Sync)
TICKTICK_CLIENT_ID=your_client_id_here
TICKTICK_CLIENT_SECRET=your_client_secret_here

# Weather
OPENWEATHER_API_KEY=your_api_key_here

# News
NEWSAPI_KEY=your_api_key_here

# AI Providers (at least one recommended)
OLLAMA_HOST=http://localhost:11434
OPENAI_API_KEY=your_openai_key_here
GEMINI_API_KEY=your_gemini_key_here
```

## Configuration Steps

### 1. Google OAuth Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable **Gmail API** and **Google Calendar API**
4. Create OAuth 2.0 credentials:
   - Application type: Web application
   - Authorized redirect URIs: `http://localhost:8008/auth/google/callback`
5. Download credentials and add to `.env`

### 2. GitHub Token

1. Go to [GitHub Settings > Developer Settings > Personal Access Tokens](https://github.com/settings/tokens)
2. Generate new token (classic)
3. Select scopes: `repo`, `user`, `notifications`
4. Add token to `.env` as `GITHUB_TOKEN`

### 3. TickTick (Optional)

1. Go to [TickTick Open Platform](https://developer.ticktick.com/)
2. Create application
3. Add OAuth credentials to `.env`

### 4. Weather API (Optional)

1. Sign up at [OpenWeatherMap](https://openweathermap.org/api)
2. Get free API key
3. Add to `.env` as `OPENWEATHER_API_KEY`

### 5. AI Provider (Recommended)

Choose at least one:

**Ollama (Local, Free)**
```bash
# Install Ollama
brew install ollama  # macOS
# or download from ollama.ai

# Pull a model
ollama pull llama2
ollama pull mistral

# Start Ollama (runs on port 11434)
ollama serve
```

**OpenAI (Cloud, Paid)**
```bash
# Get API key from platform.openai.com
OPENAI_API_KEY=sk-...
```

**Google Gemini (Cloud, Free Tier)**
```bash
# Get API key from ai.google.dev
GEMINI_API_KEY=...
```

## Manual Installation

If `startup.sh` doesn't work:

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy config examples
cp config/config.yaml.example config/config.yaml
cp config/credentials.yaml.example config/credentials.yaml

# Initialize database
python3 -c "from src.database import db; db.init_db()"

# Start server
python3 src/main.py
```

## Verify Installation

1. Open browser to `http://localhost:8008`
2. Check the health endpoint: `http://localhost:8008/health`
3. Should see JSON response: `{"status": "healthy", ...}`

## Troubleshooting

### Port Already in Use
```bash
# Find and kill process on port 8008
lsof -ti:8008 | xargs kill -9
```

### Missing Dependencies
```bash
pip install -r requirements.txt --upgrade
```

### OAuth Errors
- Verify redirect URIs match exactly in Google Cloud Console
- Check that APIs are enabled
- Ensure credentials are in `.env` file

### Database Errors
```bash
# Reinitialize database
rm data/dashboard.db
python3 -c "from src.database import db; db.init_db()"
```

### AI Provider Connection
```bash
# Test Ollama
curl http://localhost:11434/api/tags

# Test OpenAI
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

## Next Steps

- See `OPERATIONS.md` for deployment options
- See `REFERENCE.md` for API documentation
- Check `CHANGELOG.md` for latest updates
