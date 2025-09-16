# Project Structure & Organization Guide

## 📁 Standardized Project Layout

This document defines the exact structure that ALL AI assistants must follow when working on Buildly projects.

```
dashboard/                           # Root project directory
├── main.py                         # Single entry point application
├── database.py                     # Database operations and models
├── requirements.txt                # Python dependencies
├── startup.sh                      # MANDATORY startup script
├── .env                           # Environment variables (gitignored)
├── .env.example                   # Environment template
├── dashboard.db                   # SQLite database file
├── dashboard.log                  # Application logs
├── dashboard.pid                  # Process ID file
│
├── config/                        # Configuration Management
│   ├── __init__.py
│   ├── settings.py               # Configuration classes
│   ├── config.yaml               # Main configuration
│   ├── config.yaml.example       # Configuration template
│   ├── credentials.yaml          # API credentials
│   ├── credentials.yaml.example  # Credentials template
│   └── google_oauth_config.json  # OAuth configuration
│
├── collectors/                    # Data Collection Layer
│   ├── __init__.py
│   ├── base_collector.py         # Abstract base class
│   ├── calendar_collector.py     # Google Calendar integration
│   ├── email_collector.py        # Gmail integration
│   ├── github_collector.py       # GitHub API integration
│   ├── weather_collector.py      # Weather data collection
│   ├── news_collector.py         # News aggregation
│   ├── music_collector.py        # Music service integration
│   ├── vanity_alerts_collector.py # Web mentions monitoring
│   └── {service}_collector.py    # Additional service collectors
│
├── processors/                   # Data Processing & AI Layer
│   ├── __init__.py
│   ├── ai_providers.py          # Multi-provider AI interface
│   ├── ai_training_collector.py # AI training data collection
│   ├── data_processor.py        # Core data processing utilities
│   ├── insight_generator.py     # AI-powered insights
│   ├── email_analyzer.py        # Email content analysis
│   ├── kpi_calculator.py        # Key performance indicators
│   └── {specific}_processor.py  # Specialized processors
│
├── static/                       # Web Assets (Optional)
│   ├── dashboard.css            # Styles (if using separate files)
│   ├── dashboard.js             # JavaScript (if using separate files)
│   └── assets/                  # Images, fonts, etc.
│
├── scripts/                      # Utility Scripts
│   ├── setup.sh                # Initial setup script
│   ├── collect_and_generate.sh # Data collection automation
│   ├── nightly_cleanup.py      # Maintenance tasks
│   └── {purpose}_script.py     # Purpose-specific scripts
│
├── tokens/                       # OAuth & API Token Storage
│   ├── google_credentials.json  # Google OAuth tokens
│   └── {service}_tokens.json   # Service-specific tokens
│
├── data/                         # Application Data
│   ├── personality_profiles/    # AI personality configurations
│   ├── exports/                 # Data export files
│   └── backups/                 # Database backups
│
├── devdocs/                      # 📚 ALL DOCUMENTATION GOES HERE
│   ├── README.md                # Main project documentation
│   ├── index.md                 # Documentation navigation
│   ├── code-organization.md     # This file's content
│   ├── setup/                   # Installation & Configuration
│   │   ├── installation.md      # Complete setup guide
│   │   ├── startup.md           # How to start the system
│   │   ├── environment.md       # Environment configuration
│   │   └── troubleshooting.md   # Common issues & solutions
│   ├── api/                     # API Documentation
│   │   ├── endpoints.md         # API endpoint reference
│   │   ├── authentication.md    # OAuth & API key setup
│   │   ├── data-formats.md      # Request/response formats
│   │   └── examples.md          # Usage examples
│   ├── collectors/              # Data Collection Documentation
│   │   ├── overview.md          # Collector architecture
│   │   ├── creating-collectors.md # How to add new collectors
│   │   ├── gmail.md             # Gmail integration
│   │   ├── github.md            # GitHub integration
│   │   ├── weather.md           # Weather integration
│   │   └── {service}.md         # Service-specific guides
│   ├── processors/              # Processing & AI Documentation
│   │   ├── overview.md          # Processor architecture
│   │   ├── ai-providers.md      # AI provider setup
│   │   ├── training.md          # AI training system
│   │   └── analytics.md         # Data analysis features
│   ├── deployment/              # Production Deployment
│   │   ├── production.md        # Production deployment
│   │   ├── monitoring.md        # System monitoring
│   │   └── backup.md            # Backup strategies
│   └── architecture/            # System Architecture
│       ├── overview.md          # High-level architecture
│       ├── database.md          # Database design
│       ├── security.md          # Security considerations
│       └── scalability.md       # Scaling strategies
│
└── .github/                      # GitHub Configuration
    ├── workflows/               # CI/CD workflows
    ├── ISSUE_TEMPLATE/          # Issue templates
    ├── copilot-instructions.md  # GitHub Copilot instructions
    └── prompts/                 # AI Assistant Instructions
        ├── buildly-development-standards.md
        ├── project-structure.md # This file
        ├── ai-assistant-guidelines.md
        └── coding-conventions.md
```

## 🎯 Organization Principles

### 1. Single Responsibility
- **One concern per directory**
- **One service per collector**
- **One provider per AI class**
- **One purpose per script**

### 2. Layered Architecture
```
Presentation Layer    → main.py (FastAPI endpoints)
Business Logic       → processors/ (data processing, AI)
Data Access Layer    → collectors/ (external APIs)
Infrastructure       → database.py, config/
```

### 3. Configuration Hierarchy
```
1. Environment Variables (.env)         # Secrets, API keys
2. YAML Configuration (config/)         # Structured settings
3. Database Settings (dynamic)          # User preferences
4. Hardcoded Defaults (fallback)        # Last resort
```

### 4. Data Flow Pattern
```
External APIs → Collectors → Database → Processors → AI → Dashboard → User
```

## 📋 File Organization Rules

### Collectors (`collectors/`)
- **One file per service** (e.g., `gmail_collector.py`)
- **Inherit from `BaseCollector`**
- **Async methods** for non-blocking operations
- **Error handling** with graceful fallbacks
- **Standard return format** for consistency

### Processors (`processors/`)
- **Transform collected data** into useful insights
- **Implement AI capabilities** (chat, analysis, training)
- **Provide business logic** for dashboard features
- **Handle multiple data sources** for comprehensive analysis

### Configuration (`config/`)
- **settings.py**: Pydantic models for validation
- **config.yaml**: Main configuration file
- **credentials.yaml**: API keys and secrets
- **Templates**: Example files for setup

### Documentation (`devdocs/`)
- **Categorized by purpose** (setup, api, collectors, etc.)
- **Complete setup guides** for each feature
- **API documentation** with examples
- **Troubleshooting guides** for common issues
- **Architecture decisions** and rationale

## 🚨 Critical Rules

### Documentation Placement
```
✅ CORRECT: devdocs/setup/installation.md
❌ WRONG:   README.md (in root)
❌ WRONG:   SETUP.md (in root)
❌ WRONG:   docs/ (wrong folder name)
```

### Startup Process
```
✅ CORRECT: ./startup.sh
❌ WRONG:   python main.py
❌ WRONG:   python3 -m uvicorn main:app
❌ WRONG:   npm start
```

### File Naming
```
✅ CORRECT: gmail_collector.py
❌ WRONG:   GmailCollector.py
❌ WRONG:   gmail-collector.py
❌ WRONG:   gmailcollector.py
```

### Import Organization
```python
# Standard library imports
import os
import json
from datetime import datetime

# Third-party imports
import aiohttp
from fastapi import FastAPI

# Local imports
from database import db
from collectors.base_collector import BaseCollector
```

## 🔄 Development Workflow

### Adding New Features
1. **Plan structure** - Determine if collector, processor, or both
2. **Create files** - Follow naming conventions
3. **Implement code** - Use established patterns
4. **Add configuration** - Environment variables and settings
5. **Write documentation** - Complete guide in `devdocs/`
6. **Test thoroughly** - Both unit and integration tests
7. **Update main app** - Add API endpoints and UI

### Modifying Existing Features
1. **Read documentation** - Understand current implementation
2. **Check dependencies** - What else might be affected
3. **Make changes** - Follow existing patterns
4. **Update documentation** - Keep docs current
5. **Test all functions** - Ensure nothing breaks
6. **Update version info** - Track changes appropriately

This structure ensures maintainable, scalable, and well-documented projects that any developer can understand and contribute to effectively.
