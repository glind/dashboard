# Personal Dashboard - Developer Documentation

## 🏗️ Architecture Overview

The Personal Dashboard is a modern FastAPI-based application that collects data from multiple sources and displays it in a unified interface. The architecture is designed to be modular, extensible, and easy to maintain.

### System Components

```
dashboard/
├── main.py                    # Main FastAPI application and web interface
├── database.py               # SQLite database layer and ORM
├── requirements.txt          # Python dependencies
├── startup.sh               # Production startup script
├── config/                  # Configuration management
├── collectors/              # Data collection modules
├── processors/              # Data processing and AI modules
├── static/                  # Web assets (CSS, JS)
├── tokens/                  # OAuth credentials storage
└── devdocs/                 # Documentation
```

## 🚀 Quick Start

1. **Setup**: Run `./startup.sh` - this handles everything automatically
2. **Access**: Open http://localhost:8008 in your browser
3. **Configure**: Use the ⚙️ admin panels to set up data sources

## 📊 Data Sources

The dashboard supports multiple data collectors:

- **📅 Calendar**: Google Calendar events and meetings
- **📧 Email**: Gmail analytics and insights
- **🐙 GitHub**: Repository activity and commits
- **✅ TickTick**: Task management and productivity
- **📰 News**: Technology news and articles
- **🎵 Music**: Currently playing from Apple Music
- **🌤️ Weather**: Current conditions and 5-day forecast
- **🔍 Vanity Alerts**: Mentions monitoring across the web
- **🤖 AI Assistant**: Multi-provider chat with training capabilities

## 🤖 AI Assistant Features

The dashboard includes a comprehensive AI Assistant with:

- **Multi-Provider Support**: Ollama (local/network), OpenAI, Google Gemini
- **Training System**: Learns from your preferences and interactions
- **Chat Interface**: Persistent conversations with context
- **Admin Controls**: Provider configuration and training management
- **Network Support**: Connect to remote Ollama instances

## 🔧 Configuration

All configuration is managed through:

1. **Environment Variables**: API keys and credentials (`.env` file)
2. **YAML Config**: Core settings (`config/config.yaml`)
3. **Admin Interface**: Widget-specific settings via web UI
4. **Database**: Dynamic settings and user preferences

## 📝 Development

### Adding New Data Sources

1. Create a new collector in `collectors/`
2. Inherit from `BaseCollector` if available
3. Implement `collect_data()` method
4. Add API endpoint in `main.py`
5. Update frontend widget in the dashboard

### Extending AI Capabilities

1. Add new providers in `processors/ai_providers.py`
2. Implement training data collectors in `processors/ai_training_collector.py`
3. Update admin interface for new configurations

## 📚 Documentation Structure

- `setup/` - Installation and deployment guides
- `api/` - API endpoint documentation  
- `collectors/` - Data source integration guides
- `code-organization.md` - Detailed project structure and architecture
- `CLEANUP_SUMMARY.md` - Recent codebase cleanup and organization changes

## 🛡️ Security & Privacy

- All API keys stored locally in encrypted format
- OAuth tokens managed securely
- No data sent to external services except for configured integrations
- Local AI processing with Ollama for privacy

## 🚨 Production Deployment

**Always use `./startup.sh` for production deployment**

- Manages virtual environment automatically
- Handles process management with PID files
- Provides proper logging and error handling
- Supports restart and status checking

Never run `python3 main.py` directly in production!

## 🔍 Troubleshooting

1. **Dashboard won't start**: Check `dashboard.log` for errors
2. **Missing data**: Verify API keys in admin panels
3. **AI not working**: Check Ollama installation and model availability
4. **Network issues**: Verify firewall settings for port 8008

## � License

Personal use project - see main README for details.
1. Read `setup/startup.md` 
2. Run `./startup.sh`
3. Open http://localhost:8008

## 📚 Development
All documentation is organized by purpose. Start with the setup guides, then explore collectors for data integration.

## 🤖 AI Assistant Memory
AI assistant instructions and memory are stored separately in `.github/prompts/` and are automatically used by AI assistants working on this project.
