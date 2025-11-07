# Changelog

All notable changes to Personal Dashboard will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-11-05

### Added
- Initial release of Personal Dashboard
- Gmail integration with smart email analysis
- Google Calendar integration with event tracking
- Task management with TickTick sync
- GitHub activity monitoring
- RSS news aggregator with custom sources
- Weather tracking via OpenWeatherMap
- Music news from Spotify, Bandcamp, Apple Music
- AI assistant with Ollama, OpenAI, and Gemini support
- AI-powered task suggestions with duplicate filtering
- 5-minute overview summary on AI Assistant page
- Personalized suggestions based on user profile and activity
- Background image management with like/dislike feedback
- Full-page background mode with transparent cards
- User profile management for AI personalization
- News source management (add/remove/toggle)
- Dark theme with Tailwind CSS
- Auto-refresh capability (configurable interval)
- Health check endpoint for monitoring
- SQLite database for data persistence
- Docker deployment support
- Kubernetes Helm chart
- Comprehensive documentation in devdocs/

### Security
- BSL 1.1 license with Apache-2.0 change date (2027-11-05)
- OAuth 2.0 for Google services
- Token-based authentication for GitHub
- Environment variable configuration
- No hardcoded credentials

### Documentation
- Setup guide (SETUP.md)
- Operations guide (OPERATIONS.md)
- API reference (REFERENCE.md)
- Support policy (SUPPORT.md)
- License terms (LICENSE.md)
- Marketplace metadata (BUILDLY.yaml)

### Testing
- Smoke tests for health endpoint
- CRUD tests for task operations
- UI load tests
- API endpoint validation

## [Unreleased]

### Planned
- WebSocket support for real-time updates
- Mobile app (iOS/Android)
- Todoist sync alternative to TickTick
- Notion integration
- Slack/Discord notifications
- Calendar event creation from dashboard
- Email composition from dashboard
- Advanced task analytics
- Custom AI model fine-tuning
- Multi-user support
- Team dashboards
- Export/import functionality
- Backup automation
- Plugin system for custom collectors
