# TickTick Integration

## Overview
TickTick is a powerful task management platform. This integration provides OAuth-based authentication and task synchronization.

## Features
- OAuth 2.0 authentication flow
- Task list retrieval
- Task creation and updates
- Project/list management
- Due date and priority sync

## Setup

### 1. TickTick Developer Account
1. Visit [TickTick Developer Portal](https://developer.ticktick.com)
2. Create new application
3. Configure redirect URI: `http://localhost:8008/auth/ticktick/callback`
4. Note your Client ID and Client Secret

### 2. Configuration
Add to `config/credentials.yaml`:
```yaml
ticktick:
  client_id: "your_client_id_here"
  client_secret: "your_client_secret_here"
```

### 3. Authentication Flow
1. Visit dashboard at http://localhost:8008
2. Click TickTick authentication button
3. Grant permissions in TickTick
4. You'll be redirected back with access token
5. Token is stored securely for future requests

## API Endpoints

### Get Tasks
```http
GET /api/ticktick
```

Response:
```json
{
  "tasks": [
    {
      "id": "task_id",
      "title": "Task title", 
      "completed": false,
      "dueDate": "2025-09-04T12:00:00Z",
      "priority": 1
    }
  ],
  "authenticated": true
}
```

### Authentication Status
```http
GET /auth/ticktick
```

## Implementation Details

### OAuth Flow
1. User clicks auth button → `/auth/ticktick`
2. Redirect to TickTick with OAuth params
3. User grants permission
4. TickTick redirects to `/auth/ticktick/callback?code=...`
5. Exchange code for access token
6. Store token in database

### Data Sync
- Tasks cached for 5 minutes
- Only incomplete tasks shown by default
- Due dates formatted for dashboard display
- Priority levels mapped to visual indicators

## Troubleshooting

### Common Issues
- **Invalid redirect URI**: Check TickTick app settings
- **Authentication failed**: Verify client ID/secret
- **No tasks showing**: Check TickTick permissions

### Debug Mode
Enable debug logging:
```python
logging.getLogger('collectors.ticktick_collector').setLevel(logging.DEBUG)
```

## Future Enhancements
- Task creation from dashboard
- Bulk task operations
- Calendar integration
- Smart notifications
