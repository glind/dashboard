# Custom Modules System

## Overview
The custom modules system allows you to extend the Personal Dashboard with specialized functionality while maintaining a consistent architecture and reusing core services like the AI assistant.

## Architecture

### Module Structure
Each custom module should follow this structure:
```
src/modules/
├── README.md (this file)
├── __init__.py
├── music_news/
│   ├── __init__.py
│   ├── collector.py      # Data collection logic
│   ├── processor.py      # Data processing/analysis
│   └── endpoints.py      # API endpoints
└── vanity_alerts/
    ├── __init__.py
    ├── collector.py
    ├── processor.py
    └── endpoints.py
```

### Core Components

#### 1. Collector (`collector.py`)
Responsible for fetching data from external sources.

```python
from typing import Dict, Any, List

def collect_data(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Collect data from external source.
    
    Args:
        config: Configuration dict with API keys, settings, etc.
        
    Returns:
        Dict with collected data and metadata
    """
    return {
        'success': True,
        'data': [],
        'timestamp': datetime.now().isoformat(),
        'source': 'module_name'
    }
```

#### 2. Processor (`processor.py`)
Handles data processing, filtering, and AI integration.

```python
from typing import Dict, Any
from services.ai_service import get_ai_service

async def process_data(data: List[Dict], db, settings) -> Dict[str, Any]:
    """
    Process collected data and optionally use AI for analysis.
    
    Args:
        data: Raw collected data
        db: Database manager instance
        settings: Application settings
        
    Returns:
        Processed results with insights
    """
    # Use the shared AI service
    ai_service = get_ai_service(db, settings)
    
    # Example AI analysis
    result = await ai_service.chat(
        message=f"Analyze this data: {data[:3]}",
        include_context=False
    )
    
    return {
        'processed_items': data,
        'ai_insights': result.get('response'),
        'success': True
    }
```

#### 3. Endpoints (`endpoints.py`)
Defines FastAPI routes for the module.

```python
from fastapi import APIRouter, Depends
from typing import Dict, Any

router = APIRouter(prefix="/api/modules/module_name", tags=["custom_modules"])

@router.get("/data")
async def get_module_data() -> Dict[str, Any]:
    """Get module data."""
    from .collector import collect_data
    from database import get_credentials
    
    config = get_credentials('module_name') or {}
    return collect_data(config)

@router.post("/analyze")
async def analyze_with_ai(request: Dict[str, Any]) -> Dict[str, Any]:
    """Use AI to analyze module data."""
    from .processor import process_data
    from database import get_database, get_settings
    
    db = get_database()
    settings = get_settings()
    
    return await process_data(
        data=request.get('data', []),
        db=db,
        settings=settings
    )
```

## Creating a New Custom Module

### Step 1: Create Module Directory
```bash
mkdir -p src/modules/your_module
touch src/modules/your_module/__init__.py
```

### Step 2: Implement Collector
Create `src/modules/your_module/collector.py`:
```python
import requests
from typing import Dict, Any
from datetime import datetime

def collect_data(config: Dict[str, Any]) -> Dict[str, Any]:
    """Fetch data from your source."""
    api_key = config.get('api_key')
    
    try:
        # Your data collection logic
        response = requests.get(
            'https://api.example.com/data',
            headers={'Authorization': f'Bearer {api_key}'}
        )
        
        return {
            'success': True,
            'data': response.json(),
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }
```

### Step 3: Implement Processor (Optional)
Create `src/modules/your_module/processor.py` if you need AI analysis:
```python
from typing import Dict, Any, List
from services.ai_service import get_ai_service

async def process_data(
    data: List[Dict], 
    db, 
    settings,
    analysis_prompt: str = None
) -> Dict[str, Any]:
    """Process data with optional AI analysis."""
    
    # Use shared AI service
    ai_service = get_ai_service(db, settings)
    
    if analysis_prompt:
        result = await ai_service.chat(
            message=analysis_prompt,
            include_context=False
        )
        
        return {
            'processed_items': data,
            'ai_analysis': result.get('response'),
            'success': result.get('success', False)
        }
    
    return {
        'processed_items': data,
        'success': True
    }
```

### Step 4: Create API Endpoints
Create `src/modules/your_module/endpoints.py`:
```python
from fastapi import APIRouter
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/modules/your_module", tags=["custom_modules"])

@router.get("/data")
async def get_data() -> Dict[str, Any]:
    """Get module data."""
    from .collector import collect_data
    from database import get_credentials
    
    config = get_credentials('your_module') or {}
    return collect_data(config)

@router.post("/analyze")
async def analyze_data(request: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze data with AI."""
    from .processor import process_data
    from database import get_database, get_settings
    
    db = get_database()
    settings = get_settings()
    
    return await process_data(
        data=request.get('data', []),
        db=db,
        settings=settings,
        analysis_prompt=request.get('prompt')
    )
```

### Step 5: Register Module in Main App
In `src/main.py`, add your module router:
```python
# Import your module router
from modules.your_module.endpoints import router as your_module_router

# Register it
app.include_router(your_module_router)
```

### Step 6: Add UI Component
Create a section in the dashboard UI (`src/templates/dashboard.html` or `src/static/dashboard.js`):
```javascript
// Add to navigation
{
    id: 'your-module',
    label: 'Your Module',
    icon: '🎯',
    category: 'custom_modules'
}

// Add data loading
async loadYourModuleData() {
    const response = await fetch('/api/modules/your_module/data');
    this.yourModuleData = await response.json();
}

// Add AI analysis
async analyzeYourModule(prompt) {
    const response = await fetch('/api/modules/your_module/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            data: this.yourModuleData,
            prompt: prompt
        })
    });
    return await response.json();
}
```

## Configuration

### Credentials
Store module credentials in `config/credentials.yaml`:
```yaml
your_module:
  api_key: "your_api_key_here"
  api_url: "https://api.example.com"
  enabled: true
```

### Settings
Store module settings in database:
```python
db.save_setting('your_module_enabled', True)
db.save_setting('your_module_refresh_interval', 300)
```

## Using the Shared AI Service

All modules have access to the centralized AI service:

```python
from services.ai_service import get_ai_service

# Get AI service instance
ai_service = get_ai_service(db, settings)

# Chat with context
result = await ai_service.chat(
    message="Analyze this music news for trends",
    conversation_id="module_conv_123",
    include_context=True  # Includes user's dashboard context
)

# Chat without context (faster)
result = await ai_service.chat(
    message="Summarize these articles",
    include_context=False
)

# Access response
if result.get('success'):
    response = result['response']
    provider = result['provider']  # "Ollama", "OpenAI", etc.
```

## Best Practices

1. **Reuse Core Services**: Always use the shared AI service, database, and settings
2. **Error Handling**: Return consistent error structures with `success: False`
3. **Logging**: Use Python's logging module for debugging
4. **Configuration**: Store sensitive data in credentials.yaml, not in code
5. **API Design**: Follow RESTful patterns for endpoints
6. **Documentation**: Document your module's purpose, configuration, and endpoints
7. **Type Hints**: Use type hints for better code clarity
8. **Async Operations**: Use async/await for I/O operations
9. **Rate Limiting**: Respect external API rate limits
10. **Caching**: Cache expensive operations in the database

## Example Modules

### Music News
- **Purpose**: Aggregates music industry news from multiple sources
- **Location**: `src/modules/music_news/`
- **Endpoints**: 
  - `GET /api/modules/music_news/data` - Get latest music news
  - `POST /api/modules/music_news/analyze` - AI analysis of trends

### Vanity Alerts
- **Purpose**: Monitors mentions across web, social media, and news
- **Location**: `src/modules/vanity_alerts/`
- **Endpoints**:
  - `GET /api/modules/vanity_alerts/data` - Get mention alerts
  - `POST /api/modules/vanity_alerts/analyze` - AI sentiment analysis

## Troubleshooting

### Module Not Loading
- Check that `__init__.py` exists in module directory
- Verify router is registered in `main.py`
- Check logs for import errors

### AI Service Not Working
- Ensure AI provider is configured in settings
- Check that Ollama/OpenAI credentials are valid
- Verify `get_ai_service()` is called with db and settings

### Data Not Appearing
- Check collector returns correct data structure
- Verify API credentials in credentials.yaml
- Check browser console for frontend errors

## Support

For questions or issues with custom modules:
1. Check this README
2. Review example modules (music_news, vanity_alerts)
3. Check main dashboard documentation in `devdocs/`
