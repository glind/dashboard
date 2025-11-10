# Personal Dashboard

> **AI-Powered Personal Productivity Hub**

A comprehensive dashboard that integrates email, calendar, tasks, GitHub, news, music, and weather with intelligent AI assistance—all in one beautiful interface.

[![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)](LICENSE.md)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-ready-brightgreen.svg)](https://www.docker.com/)

---

## 🚀 Quick Start

```bash
# Clone repository
git clone https://github.com/buildly-marketplace/personal-dashboard.git
cd personal-dashboard

# Setup credentials (REQUIRED)
./scripts/setup-credentials.sh

# Start dashboard (handles everything automatically)  
./ops/startup.sh
```

🌐 **Dashboard URL**: http://localhost:8008

---

## 🔒 Security Setup (CRITICAL)

### ⚠️ Before First Run

The dashboard requires API credentials that are **NOT** included in this repository for security reasons.

1. **Run the setup script**:
   ```bash
   ./scripts/setup-credentials.sh
   ```

2. **Configure your credentials**:
   - Edit `src/config/credentials.yaml` with your API tokens
   - Edit `src/config/google_oauth_config.json` with your Google OAuth credentials
   - Edit `.env` with your environment variables

3. **Get API Keys**:
   - **GitHub**: https://github.com/settings/tokens (repo, read:user permissions)
   - **Google**: https://console.cloud.google.com/apis/credentials (Gmail, Calendar APIs)
   - **TickTick**: TickTick developer settings
   - **OpenWeather**: https://openweathermap.org/api
   - **News API**: https://newsapi.org/

### 🛡️ Security Best Practices

- ✅ Credential files are automatically excluded from git
- ✅ Use environment variables for production
- ✅ Never commit actual API keys
- ✅ Rotate credentials regularly

# Clone repository

# Open browsergit clone https://github.com/buildly-marketplace/personal-dashboard.git

open http://localhost:8008cd personal-dashboard

```

# Start dashboard (handles everything automatically)

### Dashboard Management./ops/startup.sh



```bash# Open browser

# Start dashboard (default action)open http://localhost:8008

./ops/startup.sh start```



# Check status and health### Dashboard Management

./ops/startup.sh status

The startup script provides comprehensive dashboard management:

# View logs (last 50 lines)

./ops/startup.sh logs```bash

# Start dashboard (default action)

# Follow logs in real-time  ./ops/startup.sh start

./ops/startup.sh logs follow

# Check status and health

# Stop dashboard./ops/startup.sh status

./ops/startup.sh stop

# View logs (last 50 lines)

# Restart dashboard./ops/startup.sh logs

./ops/startup.sh restart

# Follow logs in real-time  

# Repair corrupted database./ops/startup.sh logs follow

./ops/startup.sh repair

```# Stop dashboard

./ops/startup.sh stop

### System Requirements

# Restart dashboard

- **Python**: 3.10+ (3.11 recommended)./ops/startup.sh restart

- **APIs**: Google OAuth credentials (Gmail & Calendar), GitHub personal access token

- **Optional**: TickTick, OpenWeather, NewsAPI, AI provider (Ollama/OpenAI/Gemini)# Repair corrupted database

./ops/startup.sh repair

**🚨 CRITICAL**: Always use `./ops/startup.sh` - never run `python3 main.py` directly!

# Show help

---./ops/startup.sh help

```

## 🎯 Current Features

### System Requirements

### Data Collection

- **📅 Google Calendar** - Events, meetings, and schedule management- **Python**: 3.10+ (3.11 recommended)

- **📧 Gmail** - Email summary, unread count, and intelligent filtering- **APIs**: Google OAuth credentials (Gmail & Calendar), GitHub personal access token

- **🐙 GitHub** - Assigned issues, PR reviews, and repository activity- **Optional**: TickTick, OpenWeather, NewsAPI, AI provider (Ollama/OpenAI/Gemini)

- **📰 News** - Personalized feeds filtered by interests (Tech, AI, etc.)

- **🌤️ Weather** - Local weather conditions and forecasts**🚨 CRITICAL**: Always use `./ops/startup.sh` - never run `python3 main.py` directly!

- **✅ TickTick** - Task management with OAuth integration

- **🎵 Music** - Listening trends and recommendations---



### AI-Powered Features## 📖 Documentation

- **🤖 Insight Generation** - Intelligent analysis of your data patterns

- **📊 KPI Tracking** - Automated productivity metrics### Quick Links

- **🎯 Task Prioritization** - Smart recommendations for daily focus- **Setup Guide**: [`devdocs/setup/startup.md`](devdocs/setup/startup.md) - Complete setup instructions

- **📈 Trend Analysis** - Weekly/monthly productivity insights- **API Reference**: [`devdocs/api/endpoints.md`](devdocs/api/endpoints.md) - Available endpoints  

- **Integration Guide**: [`devdocs/collectors/overview.md`](devdocs/collectors/overview.md) - Adding data sources

### Interface- **AI Instructions**: [`.github/prompts/`](.github/prompts/) - AI assistant memory and guidelines

- **🎨 Modern UI** - Clean, responsive design with Tailwind CSS

- **🌌 Dynamic Backgrounds** - Beautiful space/sci-fi themes with image controls### Key Documents

- **📱 Mobile Friendly** - Optimized for all screen sizes- **Developer Docs**: [`devdocs/`](devdocs/) - Setup, API, and implementation guides

- **⚡ Real-time Updates** - Live data synchronization- **Project Status**: [`.github/prompts/project-status.md`](.github/prompts/project-status.md) - Current features and roadmap



### Dashboard Management---

- **📊 Status Indicators** - Real-time widget status with color coding

- **🔄 Refresh Controls** - Individual widget refresh buttons## 🎯 Current Features

- **▶️ Start/Stop Controls** - Dashboard process management from web interface

- **📝 Log Viewer** - Built-in log viewing with modal interface### Data Collection

- **📅 Google Calendar** - Events, meetings, and schedule management

---- **📧 Gmail** - Email summary, unread count, and intelligent filtering

- **🐙 GitHub** - Assigned issues, PR reviews, and repository activity

## 🔐 Security & Privacy- **📰 News** - Personalized feeds filtered by interests (Tech, AI, etc.)

- **🌤️ Weather** - Local weather conditions and forecasts

- **Local Storage**: All data stored locally in SQLite database- **✅ TickTick** - Task management with OAuth integration

- **API Security**: OAuth 2.0 for Google services, token-based for GitHub- **🎵 Music** - Listening trends and recommendations

- **Privacy**: No data transmitted to external services beyond API calls

- **Credentials**: Secure credential management with example templates### AI-Powered Features

- **🤖 Insight Generation** - Intelligent analysis of your data patterns

---- **📊 KPI Tracking** - Automated productivity metrics

- **🎯 Task Prioritization** - Smart recommendations for daily focus

## 🤝 Contributing- **📈 Trend Analysis** - Weekly/monthly productivity insights



1. Fork the repository### Interface

2. Create feature branch: `git checkout -b feature-name`- **🎨 Modern UI** - Clean, responsive design with Tailwind CSS

3. Use the startup script: `./ops/startup.sh`- **🌌 Dynamic Backgrounds** - Beautiful space/sci-fi themes with image controls

4. Test thoroughly with dashboard controls- **📱 Mobile Friendly** - Optimized for all screen sizes

5. Commit changes: `git commit -m "Add feature"`- **⚡ Real-time Updates** - Live data synchronization

6. Push branch: `git push origin feature-name`

7. Submit pull request---



---## 🔧 Architecture



## 📄 License### Backend

- **Framework**: Python FastAPI server (`src/main.py`)

**Business Source License 1.1**- **Database**: SQLite with automated integrity checks

- **APIs**: RESTful endpoints with OpenAPI documentation

- ✅ **Non-commercial use**: Free for personal and educational use- **Background Tasks**: Automated data collection and processing

- ✅ **Commercial use**: Allowed after November 5, 2027

- ✅ **Modification**: Permitted with attribution### Frontend

- 🔄 **Future**: Converts to Apache-2.0 on November 5, 2027- **Technology**: Single HTML page with embedded CSS/JavaScript  

- **Styling**: Tailwind CSS for responsive design

---- **Interactivity**: Vanilla JavaScript for dynamic content

- **Assets**: Local static files with background image management

**Built with ❤️ for personal productivity and powered by AI intelligence**

### Infrastructure  

*Part of the [Buildly Labs](https://buildly.io) ecosystem*- **Environment**: Python virtual environment with automatic setup
- **Dependencies**: Automated package installation and updates
- **Logging**: Comprehensive logging with real-time viewing
- **Process Management**: Background server with health monitoring

---

## 📦 Alternative Deployment

### Docker Deployment
```bash
# Build and run with Docker
docker-compose up -d

# View logs
docker-compose logs -f
```

### Manual Setup (Not Recommended)
If you must set up manually (not recommended):

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp config/config.yaml.example config/config.yaml
cp config/credentials.yaml.example config/credentials.yaml

# Start manually (from src directory)
cd src && python main.py
```

**⚠️ Warning**: Manual setup skips important initialization steps. Always prefer `./ops/startup.sh`.

---

## 🔐 Security & Privacy

### Data Handling
- **Local Storage**: All data stored locally in SQLite database
- **API Security**: OAuth 2.0 for Google services, token-based for GitHub
- **Privacy**: No data transmitted to external services beyond API calls
- **Credentials**: Secure credential management with example templates

### Best Practices
- **Environment Variables**: Sensitive data in `.env` files (not committed)
- **Token Management**: Automatic token refresh where supported
- **Database Security**: Regular integrity checks and repair functionality
- **Process Isolation**: Background server with controlled access

---

## 🤝 Contributing

### Development Setup
1. Fork the repository
2. Create feature branch: `git checkout -b feature-name`
3. Use the startup script: `./ops/startup.sh`
4. Test thoroughly with: `./ops/test_dashboard.sh`
5. Commit changes: `git commit -m "Add feature"`
6. Push branch: `git push origin feature-name`
7. Submit pull request

### Code Standards
- **Python**: Follow PEP 8 guidelines
- **Documentation**: Update devdocs for new features
- **Testing**: Ensure all endpoints work correctly
- **AI Memory**: Update AI instruction files for significant changes

---

## 📄 License

**Business Source License 1.1**

- ✅ **Non-commercial use**: Free for personal and educational use
- ✅ **Commercial use**: Allowed after November 5, 2027
- ✅ **Modification**: Permitted with attribution
- 🔄 **Future**: Converts to Apache-2.0 on November 5, 2027

See [LICENSE.md](LICENSE.md) for complete terms.

---

## 🆘 Support

### Getting Help
- **Documentation**: Check [`devdocs/`](devdocs/) for detailed guides
- **Issues**: Report bugs on GitHub Issues
- **Logs**: Use `./ops/startup.sh logs` for troubleshooting
- **Status**: Check server health with `./ops/startup.sh status`

### Common Issues
- **Server won't start**: Check logs and ensure port 8008 is available
- **Missing data**: Verify API credentials in `config/credentials.yaml`
- **Database errors**: Run `./ops/startup.sh repair` to fix corruption
- **Import errors**: Ensure using startup script, not manual Python execution

---

**Built with ❤️ for personal productivity and powered by AI intelligence**

*Part of the [Buildly Labs](https://buildly.io) ecosystem*