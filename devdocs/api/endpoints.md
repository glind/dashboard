# API Endpoints

## Core Data Endpoints
- `GET /` - Dashboard web interface
- `GET /api/calendar` - Google Calendar events
- `GET /api/email` - Gmail summary
- `GET /api/github` - GitHub issues and PRs
- `GET /api/news?filter=<category>` - Filtered news
- `GET /api/jokes` - Random joke
- `GET /api/weather` - Weather data
- `GET /api/ticktick` - TickTick tasks
- `GET /api/music` - Music recommendations

## News Filter Categories
- `all` - All news sources
- `tech` - Technology, Software, and AI
- `oregon` - Oregon State University
- `timbers` - Portland Timbers
- `starwars` - Star Wars content
- `startrek` - Star Trek content

## Authentication Endpoints  
- `GET /auth/ticktick` - TickTick OAuth flow
- `GET /auth/ticktick/callback` - OAuth callback

## Status Endpoints
- `GET /health` - Server health check
- `GET /api/status` - Authentication statuses

## Response Format
All endpoints return JSON:
```json
{
  "status": "success",
  "data": { ... },
  "message": "optional message"
}
```

## Error Responses
```json
{
  "status": "error", 
  "error": "Error description",
  "message": "User-friendly message"
}
```

## Rate Limiting
- Most endpoints cache data for 5-15 minutes
- External APIs are throttled to prevent rate limiting
- Real-time updates via dashboard refresh
