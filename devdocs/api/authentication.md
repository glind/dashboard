# Authentication Setup

## Google APIs (Calendar & Gmail)

### 1. Google Cloud Console Setup
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create new project or select existing
3. Enable Gmail API and Calendar API
4. Go to Credentials → Create Credentials → OAuth 2.0 Client IDs
5. Set application type to "Web application"
6. Add authorized redirect URIs:
   - `http://localhost:8008/auth/google/callback`

### 2. Download Credentials
- Download the JSON file
- Save as `config/google_oauth_config.json`

### 3. First Time Setup
- Run the dashboard
- Visit the OAuth URL in logs
- Grant permissions
- Tokens will be saved automatically

## GitHub Integration

### 1. Personal Access Token
1. Go to GitHub → Settings → Developer settings → Personal access tokens
2. Generate new token with scopes:
   - `repo` - Repository access
   - `read:user` - User information
   - `notifications` - Notification access

### 2. Configuration
Add to `config/credentials.yaml`:
```yaml
github:
  token: your_token_here
  username: your_username
```

## TickTick Integration

### 1. OAuth Application
1. Register at [TickTick Developer](https://developer.ticktick.com)
2. Create new application
3. Set redirect URI: `http://localhost:8008/auth/ticktick/callback`

### 2. Configuration
Add to `config/credentials.yaml`:
```yaml
ticktick:
  client_id: your_client_id
  client_secret: your_client_secret
```

## Weather API

### 1. Get API Key
- Sign up at [OpenWeatherMap](https://openweathermap.org/api)
- Or [WeatherAPI](https://www.weatherapi.com/)

### 2. Configuration
Add to `config/credentials.yaml`:
```yaml
weather:
  api_key: your_api_key
  location: "Portland, OR"
```

## Security Notes
- Never commit credential files to git
- Use environment variables in production
- Rotate tokens regularly
- Monitor API usage for unusual activity
