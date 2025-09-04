# Google Services Integration

## Overview
Integration with Google Calendar and Gmail APIs for personal dashboard data.

## Services
- **Google Calendar** - Upcoming events and appointments
- **Gmail** - Unread email count and recent messages

## Setup

### 1. Google Cloud Console
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create new project: "Personal Dashboard"
3. Enable APIs:
   - Gmail API
   - Google Calendar API

### 2. OAuth Credentials
1. Go to Credentials → Create Credentials → OAuth 2.0 Client IDs
2. Application type: "Web application"
3. Authorized redirect URIs:
   - `http://localhost:8008/auth/google/callback`
4. Download JSON credentials
5. Save as `config/google_oauth_config.json`

### 3. First Run Authentication
1. Start dashboard: `./startup.sh`
2. Dashboard will show Google auth URL in console
3. Visit URL and grant permissions
4. Tokens saved automatically to `tokens/google_credentials.json`

## API Integration

### Calendar Events
```python
from collectors.calendar_collector import CalendarCollector

collector = CalendarCollector(settings)
events = await collector.collect_events(start_date, end_date)
```

Features:
- Next 7 days of events
- All-day and timed events
- Proper timezone handling
- Event titles and times

### Gmail Summary
```python
from collectors.gmail_collector import GmailCollector

collector = GmailCollector(settings)
emails = await collector.collect_emails(start_date, end_date)
```

Features:
- Unread email count
- Recent email subjects and senders
- Last 24 hours of email activity
- Privacy-safe (no email content)

## Dashboard Display

### Calendar Widget
Shows next 10 upcoming events:
```
📅 Team Meeting - 9:00 AM - 10:00 AM
📅 Lunch with John - 12:00 PM  
📅 Project Review - All day
```

### Email Widget
Shows email summary:
```
📧 5 unread emails (23 total today)
- Project Update from Sarah
- Meeting Notes from Mike
- Weekly Report from System
```

## Permissions Required

### Calendar API Scopes
- `https://www.googleapis.com/auth/calendar.readonly`

### Gmail API Scopes  
- `https://www.googleapis.com/auth/gmail.readonly`

## Data Privacy
- Only metadata is accessed (no email content)
- Credentials stored locally only
- No data sent to external services
- User controls all permissions

## Troubleshooting

### Authentication Issues
```bash
# Check token status
ls -la tokens/google_credentials.json

# Re-authenticate
rm tokens/google_credentials.json
./startup.sh
```

### Common Problems
- **"Untitled Event"**: Calendar API field mapping issue
- **No emails**: Check Gmail API permissions
- **Token expired**: Dashboard auto-refreshes tokens
- **Rate limiting**: Built-in request throttling

### Debug Mode
Enable detailed logging:
```python
logging.getLogger('collectors.calendar_collector').setLevel(logging.DEBUG)
logging.getLogger('collectors.gmail_collector').setLevel(logging.DEBUG)
```
