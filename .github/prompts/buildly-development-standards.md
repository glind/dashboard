# Buildly Development Standards & Processes

## 🏗️ Core Architecture Principles

### 1. Documentation Organization
- **NEVER put documentation in root directory**
- **ALL documentation goes in `devdocs/` folder**
- **Structure**: `devdocs/{category}/{specific-topic}.md`
- **Categories**: `setup/`, `api/`, `collectors/`, `processors/`, `architecture/`

### 2. Code Organization Standards

#### Collectors Pattern (`collectors/`)
```
collectors/
├── __init__.py
├── base_collector.py        # Abstract base class
├── {service}_collector.py   # One file per service
└── README.md               # Overview in devdocs/collectors/
```

**Collector Rules:**
- Each collector inherits from `BaseCollector`
- Implement `collect_data()` method returning standardized format
- Handle errors gracefully with fallback/mock data
- Use environment variables for API keys
- Include health check methods
- Async/await for non-blocking operations

#### Processors Pattern (`processors/`)
```
processors/
├── __init__.py
├── ai_providers.py         # AI provider implementations
├── ai_training_collector.py # Training data collection
├── data_processor.py       # Core data processing
├── {specific}_processor.py # Specialized processors
```

**Processor Rules:**
- Transform and analyze data from collectors
- Provide AI capabilities and insights
- Handle multiple provider patterns (Ollama, OpenAI, etc.)
- Implement training and learning capabilities
- Separate concerns (data vs AI vs analysis)

### 3. File Naming Conventions
- **Python files**: `snake_case.py`
- **Classes**: `PascalCase` (e.g., `GmailCollector`)
- **Functions/variables**: `snake_case`
- **Constants**: `UPPER_SNAKE_CASE`
- **Config files**: `lowercase.yaml`

### 4. Database Patterns
- Use `database.py` for all DB operations
- Implement proper connection management
- Use transactions for data integrity
- Include migration capabilities
- Store settings dynamically, not hardcoded

## 🚀 Buildly Process Standards

### Development Workflow
1. **Always use `./startup.sh`** - NEVER run `python main.py` directly
2. **Environment setup first** - Configure `.env` before coding
3. **Test locally** - Verify functionality before deployment
4. **Document changes** - Update relevant `devdocs/` files
5. **Clean commits** - Descriptive commit messages

### API Design Patterns
```python
@app.get("/api/{category}")
async def get_category_data():
    """Get {category} data with error handling."""
    try:
        if COLLECTORS_AVAILABLE:
            collector = CategoryCollector()
            data = await collector.collect_data()
            return data
        else:
            return fallback_data
    except Exception as e:
        logger.error(f"Error in {category}: {e}")
        return {"error": "Failed to load data"}
```

### Configuration Management
- **Environment variables** for secrets (`.env`)
- **YAML files** for structured config (`config/`)
- **Database settings** for dynamic config
- **Admin UI** for user preferences
- **Multiple layers** with proper precedence

### Error Handling Standards
```python
try:
    # Main operation
    result = await operation()
    return result
except SpecificException as e:
    logger.error(f"Specific error: {e}")
    return fallback_response
except Exception as e:
    logger.error(f"General error: {e}")
    return {"error": "Operation failed"}
```

## 🎯 AI Assistant Integration

### Training Data Collection
- Collect user preferences from interactions
- Store in standardized format in database
- Provide context-aware responses
- Learn from likes/dislikes and usage patterns

### Provider Management
- Support multiple AI providers (Ollama, OpenAI, Gemini)
- Implement health checking for all providers
- Allow switching between providers
- Handle network and local instances

### Real-Time Context
- Always provide current data context to AI
- Never use placeholder/mock data in responses
- Query relevant database tables based on user request
- Include user profile information

## 📋 Quality Standards

### Code Quality
- **Type hints** for function parameters and returns
- **Docstrings** for all classes and public methods
- **Error logging** with appropriate levels
- **Unit tests** for critical functionality
- **Clean imports** and dependency management

### Security Practices
- Store API keys in environment variables
- Use secure OAuth flows
- Validate all user inputs
- Handle credentials safely
- Log security events appropriately

### Performance Guidelines
- Use async/await for I/O operations
- Implement caching where appropriate
- Optimize database queries
- Handle large datasets efficiently
- Monitor resource usage

## 🔧 Development Tools

### Required Tools
- **FastAPI** for web framework
- **SQLite** for database
- **Uvicorn** for ASGI server
- **Aiohttp** for async HTTP
- **PyYAML** for configuration

### Optional Integrations
- **Ollama** for local AI
- **OpenAI/Gemini** for cloud AI
- **Google APIs** for Calendar/Gmail
- **GitHub API** for repository data

## 📚 Documentation Requirements

### Every Feature Must Have
1. **Setup guide** in `devdocs/setup/`
2. **API documentation** in `devdocs/api/`
3. **Integration guide** in `devdocs/collectors/` or `devdocs/processors/`
4. **Troubleshooting section** in relevant docs
5. **Example usage** and code samples

### Documentation Format
```markdown
# Feature Name

## Overview
Brief description and purpose

## Setup
Step-by-step installation/configuration

## Usage
Code examples and API calls

## Configuration
Environment variables and settings

## Troubleshooting
Common issues and solutions
```

## ⚠️ Critical Rules

### NEVER DO
- Put documentation in root directory
- Run `python main.py` directly in production
- Hardcode API keys or secrets
- Use placeholder data in AI responses
- Skip error handling
- Mix concerns in single files

### ALWAYS DO
- Use `./startup.sh` for starting services
- Put docs in `devdocs/` with proper structure
- Follow collector/processor patterns
- Implement proper error handling
- Provide real-time data to AI
- Test with actual data

This standard ensures consistent, maintainable, and scalable development across all Buildly projects.
