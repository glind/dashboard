# Personal Dashboard

A clean, simple personal dashboard that aggregates data from your connected services.

## 🚀 Quick Start
```bash
./startup.sh
```
**Always use the startup script - never start manually!**

The script will:
- ✅ Set up and activate virtual environment
- ✅ Install/update all dependencies  
- ✅ Configure initial settings
- ✅ Start server detached on port 8008
- ✅ Verify everything is working

Open http://localhost:8008

### Other Commands
- `./startup.sh stop` - Stop the dashboard
- `./startup.sh restart` - Restart the dashboard  
- `./startup.sh status` - Check if running
- `./startup.sh logs` - View live logs

## 📖 Documentation
- **Developer Docs**: `devdocs/` - Setup, API, and implementation guides
- **AI Instructions**: `.github/prompts/` - AI assistant memory and rules

### Key Documents
- **Setup**: `devdocs/setup/startup.md` - How to start the dashboard
- **APIs**: `devdocs/api/endpoints.md` - Available endpoints
- **Integration**: `devdocs/collectors/overview.md` - Adding data sources

## 🎯 Current Features
- **📅 Google Calendar** - Your events and schedule
- **📧 Gmail** - Email summary and unread count
- **🐙 GitHub** - Assigned issues and PR reviews
- **📰 News** - Filtered by your interests (Tech, Oregon State, etc.)
- **😄 Jokes** - Single-line humor widget
- **🌤️ Weather** - Local weather display
- **✅ TickTick** - Task management (OAuth ready)
- **🎵 Music** - Trends and recommendations

## 🔧 Architecture
- **Backend**: Python FastAPI server (`main.py`)
- **Frontend**: Single HTML page with embedded CSS/JS
- **Data**: Real-time collection from authenticated APIs
- **Persistence**: SQLite database for user preferences

Built with simplicity in mind - everything in one file, real data, clean UI.

## 🛠️ Development
For implementation details, API documentation, and setup guides, see the `devdocs/` folder. AI assistants automatically use the instructions in `.github/prompts/` for consistent behavior.
