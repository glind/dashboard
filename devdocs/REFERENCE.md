# API Reference

## Base URL

```
http://localhost:8008
```

---

## Health & Status

### GET /health

Health check endpoint for monitoring.

**Response (200 OK):**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2025-11-05T10:30:00Z"
}
```

---

## Data Collection

### GET /api/data

Fetches all dashboard data (overview).

**Response (200 OK):**
```json
{
  "tasks": [...],
  "calendar": [...],
  "emails": [...],
  "github": {...},
  "news": [...],
  "weather": {...},
  "music": [...]
}
```

### POST /api/refresh

Manually trigger data refresh for all collectors.

**Response (200 OK):**
```json
{
  "status": "refreshed",
  "timestamp": "2025-11-05T10:30:00Z"
}
```

---

## Tasks

### GET /api/tasks

Get all tasks from all sources (TickTick, email-generated, manual).

**Query Parameters:**
- `completed` (bool): Filter by completion status
- `priority` (string): Filter by priority (high, medium, low)
- `source` (string): Filter by source (ticktick, email, manual)

**Response (200 OK):**
```json
[
  {
    "id": "task_123",
    "title": "Review Pull Request",
    "description": "Check PR #42 for security issues",
    "completed": false,
    "priority": "high",
    "source": "github",
    "due_date": "2025-11-06T17:00:00Z",
    "created_at": "2025-11-05T09:00:00Z"
  }
]
```

### POST /api/tasks

Create a new task.

**Request Body:**
```json
{
  "title": "Task title",
  "description": "Task description",
  "priority": "medium",
  "due_date": "2025-11-06T17:00:00Z"
}
```

**Response (201 Created):**
```json
{
  "id": "task_124",
  "title": "Task title",
  ...
}
```

### PUT /api/tasks/{task_id}

Update an existing task.

**Request Body (partial update):**
```json
{
  "completed": true,
  "priority": "high"
}
```

**Response (200 OK):**
```json
{
  "id": "task_123",
  "completed": true,
  ...
}
```

### DELETE /api/tasks/{task_id}

Delete a task.

**Response (204 No Content)**

---

## Calendar

### GET /api/calendar

Get calendar events from Google Calendar.

**Query Parameters:**
- `start` (ISO date): Start date filter
- `end` (ISO date): End date filter

**Response (200 OK):**
```json
[
  {
    "id": "event_123",
    "title": "Team Meeting",
    "description": "Weekly sync",
    "start": "2025-11-05T14:00:00Z",
    "end": "2025-11-05T15:00:00Z",
    "location": "Zoom"
  }
]
```

---

## Emails

### GET /api/emails

Get recent emails from Gmail.

**Query Parameters:**
- `unread` (bool): Filter unread only
- `priority` (string): Filter by priority (high, medium, low)
- `has_todos` (bool): Filter emails with action items

**Response (200 OK):**
```json
[
  {
    "id": "msg_123",
    "subject": "Project Update",
    "from": "alice@example.com",
    "date": "2025-11-05T08:30:00Z",
    "snippet": "Quick update on the project...",
    "read": false,
    "priority": "high",
    "has_todos": true
  }
]
```

### POST /api/emails/{email_id}/create-task

Create a task from an email.

**Response (201 Created):**
```json
{
  "task_id": "task_125",
  "email_id": "msg_123",
  "title": "Follow up: Project Update"
}
```

---

## AI Assistant

### POST /api/ai/chat

Send a message to the AI assistant.

**Request Body:**
```json
{
  "message": "What are my priorities today?",
  "conversation_id": "conv_123"
}
```

**Response (200 OK):**
```json
{
  "response": "Based on your tasks and calendar, here are your top priorities...",
  "conversation_id": "conv_123",
  "message_id": "msg_456"
}
```

### GET /api/ai/suggestions

Get AI-generated task suggestions.

**Response (200 OK):**
```json
[
  {
    "id": "suggestion_123",
    "title": "Follow up: Client Email",
    "description": "Client waiting for response about pricing",
    "priority": "high",
    "action": "create_task",
    "email_id": "msg_789"
  }
]
```

### POST /api/ai/message/feedback

Provide feedback on AI responses.

**Request Body:**
```json
{
  "message_id": "msg_456",
  "feedback_type": "rating",
  "rating": 5,
  "comment": "Very helpful"
}
```

**Response (200 OK)**

---

## User Profile

### GET /api/user/profile

Get user profile for AI personalization.

**Response (200 OK):**
```json
{
  "full_name": "John Doe",
  "preferred_name": "John",
  "occupation": "Software Engineer",
  "interests": "AI, productivity, open source",
  "timezone": "America/Los_Angeles",
  "work_hours": "9:00-17:00"
}
```

### POST /api/user/profile

Create or update user profile.

**Request Body:**
```json
{
  "full_name": "John Doe",
  "preferred_name": "John",
  "occupation": "Software Engineer",
  "interests": "AI, productivity, open source"
}
```

**Response (200 OK)**

---

## Configuration

### GET /api/config

Get current dashboard configuration.

**Response (200 OK):**
```json
{
  "collectors": {
    "gmail": true,
    "calendar": true,
    "github": true
  },
  "ai_provider": "ollama",
  "auto_refresh_minutes": 5
}
```

### PUT /api/config

Update configuration.

**Request Body:**
```json
{
  "auto_refresh_minutes": 10,
  "collectors": {
    "news": false
  }
}
```

**Response (200 OK)**

---

## News Sources

### GET /api/news-sources

Get all configured news sources.

**Response (200 OK):**
```json
[
  {
    "id": 1,
    "name": "Hacker News",
    "url": "https://hnrss.org/frontpage",
    "active": true,
    "type": "rss"
  }
]
```

### POST /api/news-sources

Add a custom news source.

**Request Body:**
```json
{
  "name": "My Blog",
  "url": "https://myblog.com/feed.xml",
  "type": "rss"
}
```

**Response (201 Created)**

### PUT /api/news-sources/{source_id}/toggle

Toggle news source active/inactive.

**Response (200 OK)**

### DELETE /api/news-sources/{source_id}

Delete a custom news source.

**Response (204 No Content)**

---

## Authentication

### GET /auth/google

Initiate Google OAuth flow for Gmail & Calendar.

**Redirects to:** Google OAuth consent screen

### GET /auth/google/callback

OAuth callback endpoint (handled automatically).

---

## Error Responses

All errors follow this format:

```json
{
  "error": "Error message",
  "detail": "Detailed explanation",
  "status_code": 400
}
```

**Common Status Codes:**
- `400` - Bad Request (invalid input)
- `401` - Unauthorized (missing auth)
- `404` - Not Found
- `429` - Rate Limited
- `500` - Internal Server Error

---

## Rate Limits

- **API endpoints:** 100 requests/minute per IP
- **AI chat:** 20 messages/minute
- **Refresh:** 1 request/minute

---

## Webhooks (Future)

Webhook support is planned for:
- New email notifications
- Calendar event reminders
- Task deadlines
- GitHub activity

---

## SDKs & Libraries

**Python:**
```python
import requests

# Get tasks
response = requests.get("http://localhost:8008/api/tasks")
tasks = response.json()
```

**JavaScript:**
```javascript
// Fetch calendar
fetch('http://localhost:8008/api/calendar')
  .then(res => res.json())
  .then(events => console.log(events));
```

**cURL:**
```bash
# Create task
curl -X POST http://localhost:8008/api/tasks \
  -H "Content-Type: application/json" \
  -d '{"title": "New Task", "priority": "high"}'
```

---

## WebSocket (Future)

Real-time updates via WebSocket planned for v2.0:

```javascript
const ws = new WebSocket('ws://localhost:8008/ws');
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Update:', data);
};
```

---

For implementation examples, see `devdocs/setup/` and `devdocs/collectors/`.
