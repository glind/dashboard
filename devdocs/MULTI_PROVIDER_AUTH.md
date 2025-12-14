# Multi-Provider Authentication System

## Overview

The dashboard now supports multiple email/calendar/notes providers through a unified authentication and data collection system:

- **Google** - Gmail, Google Calendar, Google Drive
- **Microsoft Office 365** - Outlook, Office 365 Calendar, OneNote
- **Proton** - ProtonMail (via Proton Bridge)

## Architecture

### Provider Abstraction Layer

All providers implement the `BaseProvider` interface:
```python
from providers import GoogleProvider, MicrosoftProvider, ProtonProvider, ProviderManager
```

#### Components:

1. **BaseProvider** (`src/providers/base.py`)
   - Abstract base class for all providers
   - Defines standard methods: `authenticate()`, `collect_emails()`, `collect_calendar_events()`, `collect_notes()`
   - Normalizes data to standard format

2. **ProviderManager** (`src/providers/manager.py`)
   - Manages multiple provider instances
   - Coordinates data collection across providers
   - Handles provider registration and configuration

3. **Provider Implementations**:
   - `GoogleProvider` - Google APIs integration
   - `MicrosoftProvider` - Microsoft Graph API integration
   - `ProtonProvider` - IMAP Bridge integration

## Setup

### Google Provider

1. **Google Cloud Console Setup** (existing)
   - Already configured via `config/google_oauth_config.json`
   - Scopes: Gmail, Calendar, Drive (readonly)

2. **Usage**:
   ```python
   from providers import GoogleProvider, ProviderManager
   from config.settings import Settings
   from database import DatabaseManager
   
   settings = Settings()
   db = DatabaseManager()
   provider_manager = ProviderManager(db)
   
   # Register Google provider
   google = GoogleProvider("google_personal", settings, db)
   provider_manager.register_provider(google)
   
   # Authenticate
   await google.authenticate()
   
   # Collect data
   emails = await google.collect_emails(start_date, end_date)
   ```

### Microsoft Office 365 Provider

1. **Azure App Registration**:
   ```bash
   # Go to https://portal.azure.com
   # Navigate to: Azure Active Directory → App registrations → New registration
   
   # Application name: Personal Dashboard
   # Supported account types: Accounts in any organizational directory and personal Microsoft accounts
   # Redirect URI: http://localhost:8008/auth/microsoft/callback
   ```

2. **Get Credentials**:
   - Copy Application (client) ID
   - Create Client Secret under "Certificates & secrets"
   - Add to `.env`:
     ```
     MICROSOFT_CLIENT_ID=your_client_id
     MICROSOFT_CLIENT_SECRET=your_client_secret
     ```

3. **API Permissions** (in Azure portal):
   - Microsoft Graph → Delegated permissions:
     - `Mail.Read` - Read user mail
     - `Calendars.Read` - Read user calendars
     - `Notes.Read` - Read user OneNote notebooks
     - `offline_access` - Maintain access to data

4. **Usage**:
   ```python
   from providers import MicrosoftProvider
   
   microsoft = MicrosoftProvider("microsoft_work", settings, db)
   provider_manager.register_provider(microsoft)
   
   # Get auth URL
   auth_url = await microsoft.get_auth_url()
   print(f"Visit: {auth_url}")
   
   # After OAuth callback with code
   await microsoft.handle_callback(code, state)
   
   # Collect data
   emails = await microsoft.collect_emails(start_date, end_date)
   ```

### Proton Provider

1. **Install Proton Bridge**:
   ```bash
   # Download from: https://proton.me/mail/bridge
   # macOS: Install Proton Bridge.app
   # Start the Bridge application
   ```

2. **Configure Bridge**:
   - Open Proton Bridge
   - Log in with your ProtonMail account
   - Bridge provides IMAP credentials (different from web password!)
   - Note the Bridge password shown in settings

3. **Add to `.env`**:
   ```
   PROTON_USERNAME=your_protonmail@proton.me
   PROTON_PASSWORD=bridge_password_from_app
   PROTON_IMAP_HOST=localhost
   PROTON_IMAP_PORT=1143
   ```

4. **Usage**:
   ```python
   from providers import ProtonProvider
   
   proton = ProtonProvider("proton_personal", settings, db)
   provider_manager.register_provider(proton)
   
   # Authenticate (via IMAP)
   await proton.authenticate()
   
   # Collect emails
   emails = await proton.collect_emails(start_date, end_date)
   ```

   **Note**: Proton only supports email via Bridge (no calendar/notes)

## Multi-Provider Data Collection

### Collect from All Providers

```python
from datetime import datetime, timedelta
from providers import ProviderManager

provider_manager = ProviderManager(db)

# Register all providers
provider_manager.register_provider(google)
provider_manager.register_provider(microsoft)
provider_manager.register_provider(proton)

# Collect all emails
start_date = datetime.now() - timedelta(days=7)
end_date = datetime.now()

all_emails = await provider_manager.collect_all_emails(start_date, end_date)
# Returns: {
#   "google_personal": [...emails],
#   "microsoft_work": [...emails],
#   "proton_personal": [...emails]
# }

# Collect all calendar events
all_events = await provider_manager.collect_all_calendar_events(start_date, end_date)
# Returns: {
#   "google_personal": [...events],
#   "microsoft_work": [...events]
# }

# Collect all notes
all_notes = await provider_manager.collect_all_notes()
```

### Unified Data Format

All providers normalize data to standard format:

#### Email Format:
```python
{
    'id': 'provider_specific_id',
    'provider': 'google|microsoft|proton',
    'provider_id': 'google_personal',
    'subject': 'Email subject',
    'sender': 'sender@example.com',
    'recipient': 'you@example.com',
    'body': 'Email body content',
    'snippet': 'Preview text...',
    'received_date': '2024-01-15T10:30:00Z',
    'read': True,
    'labels': ['INBOX', 'IMPORTANT'],
    'has_attachments': False,
    'is_important': True,
    'raw_data': {...}  # Provider-specific data
}
```

#### Calendar Event Format:
```python
{
    'id': 'event_id',
    'provider': 'google|microsoft',
    'provider_id': 'google_personal',
    'title': 'Meeting Title',
    'description': 'Meeting description',
    'start_time': '2024-01-15T14:00:00Z',
    'end_time': '2024-01-15T15:00:00Z',
    'all_day': False,
    'location': 'Conference Room A',
    'attendees': ['attendee1@example.com', 'attendee2@example.com'],
    'organizer': 'organizer@example.com',
    'raw_data': {...}
}
```

#### Note Format:
```python
{
    'id': 'note_id',
    'provider': 'google|microsoft',
    'provider_id': 'google_personal',
    'title': 'Note Title',
    'content': 'Note content...',
    'created_date': '2024-01-10T09:00:00Z',
    'modified_date': '2024-01-15T11:30:00Z',
    'tags': ['meeting', 'project-x'],
    'folder': 'folder_id',
    'raw_data': {...}
}
```

## API Endpoints

### Authentication Status

```bash
GET /api/providers/status
```

Returns authentication status for all providers:
```json
{
  "google_personal": {
    "provider_name": "google",
    "authenticated": true,
    "capabilities": ["email", "calendar", "notes"]
  },
  "microsoft_work": {
    "provider_name": "microsoft",
    "authenticated": true,
    "capabilities": ["email", "calendar", "notes"]
  },
  "proton_personal": {
    "provider_name": "proton",
    "authenticated": false,
    "capabilities": ["email"]
  }
}
```

### OAuth Flow

#### Microsoft OAuth:
```bash
# 1. Get auth URL
GET /api/providers/microsoft/{provider_id}/auth

# 2. User visits URL, grants permissions

# 3. Callback (automatic)
GET /auth/microsoft/callback?code=xxx&state=provider_id
```

#### Google OAuth:
```bash
# Uses existing OAuth flow
GET /auth/google/authorize
GET /auth/google/callback
```

### Data Collection

```bash
# Collect emails from all providers
GET /api/providers/emails?days=7

# Collect calendar events from all providers
GET /api/providers/calendar?days=7

# Collect notes from all providers
GET /api/providers/notes
```

## Migration from Single Provider

### Current GmailCollector Usage:
```python
# Old way
from collectors.gmail_collector import GmailCollector
collector = GmailCollector(settings)
emails = await collector.collect_data()
```

### New Multi-Provider Way:
```python
# New way
from providers import ProviderManager, GoogleProvider

provider_manager = ProviderManager(db)
google = GoogleProvider("google_personal", settings, db)
provider_manager.register_provider(google)

# Collect from all providers
all_emails = await provider_manager.collect_all_emails(start_date, end_date)
google_emails = all_emails["google_personal"]
```

### Backward Compatibility

The existing `GmailCollector` still works. The new provider system is additive.

## Database Schema

### Provider Configuration Table

```sql
CREATE TABLE provider_configs (
    provider_id TEXT PRIMARY KEY,
    provider_name TEXT NOT NULL,
    enabled INTEGER DEFAULT 1,
    capabilities TEXT NOT NULL,
    config_data TEXT,
    last_auth_date TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

### Authentication Tokens Table (existing)

```sql
CREATE TABLE comms_auth (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    user_identifier TEXT,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    token_type TEXT,
    expires_at TEXT,
    scope TEXT,
    metadata TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(platform)
);
```

Tokens are stored with platform key: `microsoft_{provider_id}`, `proton_{provider_id}`

## Security Considerations

1. **Credentials Storage**:
   - OAuth tokens stored encrypted in database
   - Proton Bridge password in `.env` (not committed to git)
   - Microsoft client secret in `.env`

2. **Token Refresh**:
   - Google: Auto-refresh handled by google-auth library
   - Microsoft: Manual refresh before expiration
   - Proton: IMAP connection maintained

3. **Scope Minimal Access**:
   - All providers use readonly scopes
   - No write/send/delete permissions

## Troubleshooting

### Google Issues:
```bash
# Token expired
rm tokens/google_credentials.json
./startup.sh  # Re-authenticate
```

### Microsoft Issues:
```bash
# Check Azure app permissions
# Verify redirect URI matches exactly
# Check client secret hasn't expired
```

### Proton Issues:
```bash
# Verify Bridge is running
ps aux | grep "proton-bridge"

# Test IMAP connection
telnet localhost 1143

# Check Bridge logs (macOS)
~/Library/Logs/protonmail/bridge/
```

### Provider Status:
```bash
# Check authentication status
curl http://localhost:8008/api/providers/status | python3 -m json.tool
```

## Future Enhancements

1. **Additional Providers**:
   - Yahoo Mail
   - iCloud Mail
   - FastMail
   - Custom IMAP/CalDAV

2. **Advanced Features**:
   - Cross-provider search
   - Unified inbox view
   - Smart deduplication (same email in multiple accounts)
   - Provider-specific filters and rules

3. **Performance**:
   - Parallel data collection
   - Incremental sync
   - Caching layer

## Example: Complete Setup

```python
# main.py - Initialize providers

from providers import ProviderManager, GoogleProvider, MicrosoftProvider, ProtonProvider
from config.settings import Settings
from database import DatabaseManager

# Initialize
settings = Settings()
db = DatabaseManager()
provider_manager = ProviderManager(db)

# Register providers
google_personal = GoogleProvider("google_personal", settings, db)
google_work = GoogleProvider("google_work", settings, db)
microsoft_work = MicrosoftProvider("microsoft_work", settings, db)
proton_personal = ProtonProvider("proton_personal", settings, db)

provider_manager.register_provider(google_personal)
provider_manager.register_provider(google_work)
provider_manager.register_provider(microsoft_work)
provider_manager.register_provider(proton_personal)

# Authenticate all
for provider in provider_manager.providers.values():
    await provider.authenticate()

# Collect unified data
from datetime import datetime, timedelta

start = datetime.now() - timedelta(days=7)
end = datetime.now()

all_emails = await provider_manager.collect_all_emails(start, end)
all_events = await provider_manager.collect_all_calendar_events(start, end)
all_notes = await provider_manager.collect_all_notes()

# Process unified data
total_emails = sum(len(emails) for emails in all_emails.values())
print(f"Collected {total_emails} emails from {len(all_emails)} providers")
```
