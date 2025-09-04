# Weather Integration

## Overview
Weather collector provides current conditions and forecast data for the dashboard widget.

## Features
- Current temperature and conditions
- 5-day forecast
- Weather alerts and warnings
- Location-based or manual location
- Multiple weather data sources

## Setup

### 1. Weather API Key
Choose one weather provider:

**OpenWeatherMap** (Recommended)
1. Sign up at https://openweathermap.org/api
2. Subscribe to Current Weather Data (free tier available)
3. Get your API key

**WeatherAPI**
1. Sign up at https://www.weatherapi.com/
2. Get free API key (1M calls/month)

### 2. Configuration
Add to `config/credentials.yaml`:
```yaml
weather:
  provider: "openweathermap"  # or "weatherapi"
  api_key: "your_api_key_here"
  location: "Portland, OR"    # or coordinates: "45.5152,-122.6784"
  units: "imperial"           # "metric" for Celsius
```

## API Endpoints

### Current Weather
```http
GET /api/weather
```

Response:
```json
{
  "current": {
    "temperature": 72,
    "condition": "Partly Cloudy",
    "humidity": 65,
    "windSpeed": 8,
    "icon": "partly-cloudy"
  },
  "forecast": [
    {
      "date": "2025-09-04",
      "high": 78,
      "low": 62,
      "condition": "Sunny"
    }
  ],
  "location": "Portland, OR"
}
```

## Widget Display
Weather appears as a small top-level widget showing:
- Current temperature
- Weather icon
- Brief condition (e.g., "Partly Cloudy")
- Click for detailed forecast

## Data Sources

### OpenWeatherMap
- **Free Tier**: 1000 calls/day, current + 5-day forecast
- **Paid Tiers**: Higher limits, hourly forecasts, historical data
- **Coverage**: Global
- **Update Frequency**: Every 10 minutes

### WeatherAPI
- **Free Tier**: 1M calls/month
- **Features**: Current, forecast, astronomy, sports
- **Coverage**: Global
- **Update Frequency**: Real-time

## Implementation Details

### Caching
- Weather data cached for 10 minutes
- Fallback to cached data if API fails
- Graceful degradation with basic info

### Location Handling
```python
# By city name
location = "Portland, OR"

# By coordinates (more accurate)
location = "45.5152,-122.6784"

# Auto-detection (requires IP geolocation)
location = "auto"
```

### Error Handling
- Network timeouts → Show cached data
- Invalid API key → Show "Weather unavailable"
- Invalid location → Fallback to default location
- Rate limiting → Extend cache duration

## Customization

### Units
- **Imperial**: Fahrenheit, mph, inches
- **Metric**: Celsius, km/h, mm

### Display Options
```python
# Minimal widget
show_details = False

# Full weather widget  
show_details = True
include_forecast = True
show_alerts = True
```

## Troubleshooting

### Common Issues
- **No data showing**: Check API key and location
- **Wrong location**: Verify location format
- **Rate limited**: Check API usage and caching
- **Stale data**: Verify cache timeout settings

### Debug Commands
```bash
# Test weather API directly
curl "http://localhost:8008/api/weather"

# Check logs
tail -f dashboard.log | grep weather
```
