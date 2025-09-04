# Data Collectors Overview

## Active Collectors

### Core Collectors
- **CalendarCollector** - Google Calendar events
- **GmailCollector** - Email summary and unread count
- **GitHubCollector** - Assigned issues and PR reviews
- **NewsCollector** - Filtered news by user interests

### Widget Collectors
- **JokesCollector** - Random jokes for humor
- **WeatherCollector** - Local weather data
- **MusicCollector** - Music trends and recommendations

### Advanced Collectors
- **TickTickCollector** - Task management integration
- **VanityAlertsCollector** - Custom mentions and alerts
- **NetworkCollector** - Network monitoring

## Collector Architecture

### Base Class
All collectors inherit from `BaseCollector` and implement:
```python
async def collect_data() -> Dict[str, Any]:
    """Main data collection method"""
    pass
```

### Common Features
- **Error Handling** - Graceful fallbacks for API failures
- **Caching** - Prevent rate limiting with intelligent caching
- **User Preferences** - Learn from user feedback
- **Database Integration** - Store credentials and preferences

### Data Flow
1. Dashboard requests data via API endpoint
2. Collector fetches from external source
3. Data is processed and formatted
4. Response cached for performance
5. User feedback stored for learning

## Adding New Collectors

### 1. Create Collector Class
```python
from collectors.base_collector import BaseCollector

class MyCollector(BaseCollector):
    async def collect_data(self):
        # Implementation
        return {"data": "example"}
```

### 2. Add API Endpoint
In `simple_main.py`:
```python
@app.get("/api/mycollector")
async def get_my_data():
    collector = MyCollector()
    return await collector.collect_data()
```

### 3. Update Frontend
Add JavaScript to fetch and display the data:
```javascript
async function loadMyData() {
    const response = await fetch('/api/mycollector');
    const data = await response.json();
    // Update DOM
}
```

### 4. Add Configuration
If needed, add settings to `config/credentials.yaml`

## Performance Considerations
- Use async/await for all HTTP requests
- Implement proper caching (5-15 minute TTL)
- Handle rate limits gracefully
- Provide meaningful fallback data
- Log errors without exposing sensitive info
