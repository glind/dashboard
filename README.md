# Personal Dashboard# Personal Dashboard



> **AI-Powered Personal Productivity Hub**A clean, simple personal dashboard that aggregates data from your connected services.



A comprehensive dashboard that integrates email, calendar, tasks, GitHub, news, music, and weather with intelligent AI assistance—all in one beautiful interface.## 🚀 Quick Start

```bash

[![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)](LICENSE.md)./startup.sh

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)```

[![Docker](https://img.shields.io/badge/docker-ready-brightgreen.svg)](https://www.docker.com/)**Always use the startup script - never start manually!**



---The script will:

- ✅ Set up and activate virtual environment

## ✨ Features- ✅ Install/update all dependencies  

- ✅ Configure initial settings

- **📧 Email Intelligence** - Gmail integration with AI-powered analysis and task extraction- ✅ Start server detached on port 8008

- **📅 Calendar Sync** - Google Calendar with event tracking and reminders- ✅ Verify everything is working

- **✅ Smart Tasks** - TickTick sync, email-to-task conversion, priority management

- **🤖 AI Assistant** - Chat, suggestions, and personalized recommendationsOpen http://localhost:8008

- **💻 GitHub Activity** - Repo monitoring, PR tracking, issue notifications

- **📰 News Aggregator** - Customizable RSS feeds from 15+ sources### Other Commands

- **🎵 Music News** - Spotify, Bandcamp, Apple Music updates- `./startup.sh stop` - Stop the dashboard

- **🌤️ Weather** - Current conditions and 5-day forecast- `./startup.sh restart` - Restart the dashboard  

- **🎨 Customization** - Dark theme, custom backgrounds, section controls- `./startup.sh status` - Check if running

- `./startup.sh logs` - View live logs

---

## 📖 Documentation

## 🚀 Quick Start- **Developer Docs**: `devdocs/` - Setup, API, and implementation guides

- **AI Instructions**: `.github/prompts/` - AI assistant memory and rules

```bash

# Clone repository### Key Documents

git clone https://github.com/buildly-marketplace/personal-dashboard.git- **Setup**: `devdocs/setup/startup.md` - How to start the dashboard

cd personal-dashboard- **APIs**: `devdocs/api/endpoints.md` - Available endpoints

- **Integration**: `devdocs/collectors/overview.md` - Adding data sources

# Run startup script (handles everything)

./ops/startup.sh## 🎯 Current Features

- **📅 Google Calendar** - Your events and schedule

# Open browser- **📧 Gmail** - Email summary and unread count

open http://localhost:8008- **🐙 GitHub** - Assigned issues and PR reviews

```- **📰 News** - Filtered by your interests (Tech, Oregon State, etc.)

- **😄 Jokes** - Single-line humor widget

### Requirements- **🌤️ Weather** - Local weather display

- **✅ TickTick** - Task management (OAuth ready)

- Python 3.10+ (3.11 recommended)- **🎵 Music** - Trends and recommendations

- Google OAuth credentials (Gmail & Calendar)

- GitHub personal access token## 🔧 Architecture

- Optional: TickTick, OpenWeather, NewsAPI, AI provider (Ollama/OpenAI/Gemini)- **Backend**: Python FastAPI server (`main.py`)

- **Frontend**: Single HTML page with embedded CSS/JS

**Detailed setup:** See [`devdocs/SETUP.md`](devdocs/SETUP.md)- **Data**: Real-time collection from authenticated APIs

- **Persistence**: SQLite database for user preferences

---

Built with simplicity in mind - everything in one file, real data, clean UI.

## 📦 Deployment

## 🛠️ Development

### Docker (Recommended)For implementation details, API documentation, and setup guides, see the `devdocs/` folder. AI assistants automatically use the instructions in `.github/prompts/` for consistent behavior.


```bash
docker-compose -f ops/docker-compose.yml up -d
```

### Kubernetes

```bash
helm install dashboard buildly/personal-dashboard
```

### Local

```bash
./ops/startup.sh
```

**Full deployment guides:** See [`devdocs/OPERATIONS.md`](devdocs/OPERATIONS.md)

---

## 🎯 What's New in v1.0

- **Smart AI Assistant** with duplicate task filtering and personalized suggestions
- **5-Minute Overview** summary on AI Assistant page
- **Background Management** with like/dislike feedback and custom uploads
- **News Source Management** with add/remove/toggle capabilities
- **Full-page backgrounds** with transparent cards
- **Settings persistence** across sessions

**Full release notes:** See [`devdocs/RELEASE_NOTES.md`](devdocs/RELEASE_NOTES.md)

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [**SETUP.md**](devdocs/SETUP.md) | Installation, configuration, environment variables |
| [**OPERATIONS.md**](devdocs/OPERATIONS.md) | Deployment (Docker, K8s, local) and maintenance |
| [**REFERENCE.md**](devdocs/REFERENCE.md) | API endpoints, request/response formats |
| [**CHANGELOG.md**](devdocs/CHANGELOG.md) | Detailed version history |
| [**RELEASE_NOTES.md**](devdocs/RELEASE_NOTES.md) | Feature highlights and migration guides |

---

## 🛡️ License & Support

### License

**BSL 1.1 → Apache-2.0** (Change Date: November 5, 2027)

- ✅ Free for personal use, development, and evaluation
- ✅ Production use with <100 active users
- ℹ️ Commercial licenses available for larger deployments

See [`LICENSE.md`](LICENSE.md) for complete terms.

### Support

**30-day installation support included** with every deployment.

- **Community:** GitHub Issues (2-5 days, best-effort)
- **Buildly Labs Customers:** 24-hour guaranteed response

See [`SUPPORT.md`](SUPPORT.md) for details and contact information.

---

## 🧪 Testing

```bash
# Install test dependencies
pip install -r tests/requirements.txt

# Run smoke tests
pytest tests/test_smoke.py -v
```

Tests cover:
- Health endpoint validation
- Basic CRUD operations
- UI load checks
- API endpoint responses

---

## 🤝 Contributing

We welcome contributions! Please:

1. Check existing [Issues](https://github.com/buildly-marketplace/personal-dashboard/issues)
2. Fork the repository
3. Create a feature branch
4. Follow code style (see `devdocs/`)
5. Add tests for new features
6. Submit a pull request

---

## 🔒 Security

Report security vulnerabilities to: **security@buildly.io**

- Do not open public issues for security bugs
- We'll respond within 48 hours
- See `devdocs/SECURITY.md` for responsible disclosure policy

---

## 🌟 Screenshots

### Dashboard Overview
![Overview](assets/screenshot-overview.png)

### AI Assistant
![AI Assistant](assets/screenshot-ai-assistant.png)

### Task Management
![Tasks](assets/screenshot-tasks.png)

---

## 📊 Marketplace

Available on **[Buildly Forge](https://buildly.io/marketplace/personal-dashboard)**

- One-click deployment
- Integrated billing
- Buildly Labs customers get 50% discount
- 30-day support included

---

## 🔗 Links

- **Repository:** [github.com/buildly-marketplace/personal-dashboard](https://github.com/buildly-marketplace/personal-dashboard)
- **Documentation:** [docs.buildly.io/personal-dashboard](https://docs.buildly.io/personal-dashboard)
- **Marketplace:** [buildly.io/marketplace/personal-dashboard](https://buildly.io/marketplace/personal-dashboard)
- **Support:** [support.buildly.io](https://support.buildly.io)

---

## 📄 Metadata

```yaml
Name: Personal Dashboard
Version: 1.0.0
License: BSL-1.1 → Apache-2.0
Targets: docker, kubernetes, github-pages, local
Python: 3.10+
Category: Productivity, AI Tools, Dashboards
```

See [`BUILDLY.yaml`](BUILDLY.yaml) for complete marketplace metadata.

---

**Built with ❤️ by Buildly Labs**

*Ship fast, keep it simple, stay open.*
