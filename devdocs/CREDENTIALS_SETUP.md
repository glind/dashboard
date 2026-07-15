# 🔐 Credentials Setup Guide

## Overview

This project uses a secure credential management system that keeps sensitive data **OUT** of version control while providing easy setup for developers.

## 🎯 Quick Start

```bash
# 1. Copy example files to real config files
./scripts/setup_credentials.sh

# 2. Edit the files with your real credentials
nano config/credentials.yaml
nano config/google_oauth_config.json

# 3. Start the dashboard
./ops/startup.sh
```

## 📁 File Structure

```
config/
├── config.yaml.example          ✅ CHECKED IN (safe template)
├── config.yaml                  ❌ GITIGNORED (your settings)
├── credentials.yaml.example     ✅ CHECKED IN (safe template)
├── credentials.yaml             ❌ GITIGNORED (your API keys)
├── google_oauth_config.json.example  ✅ CHECKED IN (safe template)
└── google_oauth_config.json     ❌ GITIGNORED (your OAuth secrets)

tokens/                          ❌ GITIGNORED (OAuth tokens)
.env                            ❌ GITIGNORED (environment vars)
```

## 🔒 What Gets Committed

### ✅ Safe to Commit
- `*.example` files (templates with placeholder values)
- Documentation files
- Setup scripts
- `.gitignore` file

### ❌ NEVER Commit
- Real credential files (`config.yaml`, `credentials.yaml`)
- OAuth config files (`google_oauth_config.json`)
- Token files (`tokens/**`)
- Environment files (`.env`)
- Any file with real API keys, passwords, or secrets

## 🛠️ Setup Instructions

### 1. Run Setup Script

The setup script copies all example files to their working locations:

```bash
./scripts/setup_credentials.sh
```

This creates:
- `config/config.yaml` (from `.example`)
- `config/credentials.yaml` (from `.example`)
- `config/google_oauth_config.json` (from `.example`)
- `.env` (from `.example`)
- Required directories (`tokens/`, `data/voice_cache/`, etc.)

### 2. Configure Google APIs

#### Get Google OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable APIs:
   - Gmail API
   - Google Calendar API
4. Go to "Credentials" → "Create Credentials" → "OAuth client ID"
5. Choose "Desktop app" as application type
6. Download the JSON file
7. Save as `config/google_oauth_config.json`

**Format:**
```json
{
  "installed": {
    "client_id": "your-client-id.apps.googleusercontent.com",
    "client_secret": "your-secret",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "redirect_uris": ["http://localhost"]
  }
}
```

### 3. Configure Other Services

Edit `config/credentials.yaml`:

```yaml
github:
  token: "ghp_YourGitHubPersonalAccessToken"
  username: "your-github-username"

todoist:
  api_token: "your-todoist-api-token"

ticktick:
  username: "your-email@example.com"
  password: "your-password"

openweather:
  api_key: "your-openweather-api-key"
  location: "Your City,US"

newsapi:
  api_key: "your-newsapi-key"

lastfm:
  api_key: "your-lastfm-api-key"
  api_secret: "your-lastfm-secret"
  username: "your-lastfm-username"
  password: "your-lastfm-password"
```

### 4. Environment Variables (Optional)

For production or Docker deployments, use `.env`:

```bash
# Database
DATABASE_URL=sqlite:///dashboard.db

# API Keys
GITHUB_TOKEN=ghp_your_token
TODOIST_TOKEN=your_todoist_token
OPENWEATHER_API_KEY=your_key
NEWSAPI_KEY=your_key

# Ollama
OLLAMA_HOST=localhost
OLLAMA_PORT=11434
OLLAMA_MODEL=qwen3:1.7b
```

## 🔄 Update Family Members

For family member setups (Greg, Sophie, etc.):

```bash
# This copies YOUR config to a family member's directory
./update_family.sh greg
```

This script:
1. Copies configs to `family/greg/`
2. Updates paths in the configs
3. Maintains gitignore protection

## 🚨 Emergency: Credentials Leaked?

If credentials are accidentally committed:

1. **Immediately revoke/rotate ALL exposed credentials**
2. Remove from git history:
   ```bash
   # Install BFG Repo Cleaner
   brew install bfg  # or download from https://rtyley.github.io/bfg-repo-cleaner/
   
   # Remove credentials file
   bfg --delete-files credentials.yaml
   
   # Clean up
   git reflog expire --expire=now --all
   git gc --prune=now --aggressive
   
   # Force push (WARNING: Destructive)
   git push --force
   ```

3. **Update `.gitignore` if needed**
4. **Generate new credentials**

## 🧪 Testing Setup

Verify your credentials are configured correctly:

```bash
# Test Google Calendar connection
curl http://localhost:8008/api/calendar

# Test GitHub connection  
curl http://localhost:8008/api/github/issues

# Check voice system
curl -X POST http://localhost:8008/api/voice/test \
  -H "Content-Type: application/json" \
  -d '{"text": "Testing credentials setup"}'
```

## 📚 Best Practices

1. **Never hardcode credentials** - Use config files or environment variables
2. **Use different credentials per environment** - dev, staging, production
3. **Rotate credentials regularly** - Change keys every 90 days
4. **Use least privilege** - Only grant necessary permissions
5. **Monitor for leaks** - Use tools like `git-secrets` or `truffleHog`
6. **Document clearly** - Update `.example` files when adding new credentials
7. **Encrypt in production** - Use secrets managers (AWS Secrets Manager, HashiCorp Vault)

## 🐛 Troubleshooting

### "No Google credentials file found"
- Run `./scripts/setup_credentials.sh`
- Verify `config/google_oauth_config.json` exists and has valid JSON

### "Authentication failed"
- Check API key is correct and not expired
- Verify API permissions are enabled
- Check firewall/network settings

### "Missing credentials.yaml"
- Run setup script: `./scripts/setup_credentials.sh`
- Edit file with real values (don't leave placeholders)

### Changes not taking effect
- Restart the dashboard: `./ops/startup.sh`
- Check for syntax errors in YAML/JSON files
- Verify file paths are correct

## 📖 Related Documentation

- [Setup Guide](SETUP.md) - Initial project setup
- [Operations Guide](OPERATIONS.md) - Running and maintaining
- [Security Audit](SECURITY_AUDIT.md) - Security review
- [Provider Setup](PROVIDER_SETUP.md) - AI provider configuration
