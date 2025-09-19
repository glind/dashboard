"""
Weather data collector using OpenWeatherMap API.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import aiohttp
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class WeatherData:
    """Weather information container."""
    temperature: float
    feels_like: float
    humidity: int
    pressure: int
    description: str
    icon: str
    wind_speed: float
    wind_direction: int
    visibility: int
    uv_index: Optional[float]
    location: str
    timestamp: datetime


@dataclass
class ForecastData:
    """Weather forecast container."""
    date: datetime
    temperature_high: float
    temperature_low: float
    description: str
    icon: str
    precipitation_chance: int


class WeatherCollector:
    """Collects current weather and forecast data."""
    
    def __init__(self, settings=None):
        """Initialize weather collector."""
        # Import here to avoid circular imports
        from config.settings import settings as default_settings
        
        self.settings = settings or default_settings
        self.api_key = self.settings.weather.api_key or os.getenv('OPENWEATHER_API_KEY')
        self.base_url = "https://api.openweathermap.org/data/2.5"
        
        # Use settings for location (default: Oregon City, OR)
        self.lat = self.settings.weather.lat
        self.lon = self.settings.weather.lon
        self.location_name = self.settings.weather.location
        self.units = self.settings.weather.units
    
    async def get_current_weather(self) -> Optional[WeatherData]:
        """Get current weather data."""
        if not self.api_key or self.api_key == 'your_openweather_api_key':
            # Return mock data if no API key
            return self._get_mock_weather()
        
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/weather"
                params = {
                    'lat': self.lat,
                    'lon': self.lon,
                    'appid': self.api_key,
                    'units': self.units
                }
                
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return self._parse_weather_data(data)
                    else:
                        logger.warning(f"Weather API returned status {response.status}")
                        return self._get_mock_weather()
                        
        except Exception as e:
            logger.warning(f"Failed to fetch weather data: {e}")
            return self._get_mock_weather()
    
    async def get_forecast(self, days: int = 5) -> list[ForecastData]:
        """Get weather forecast for the next few days."""
        if not self.api_key or self.api_key == 'your_openweather_api_key':
            # Return mock data if no API key
            return self._get_mock_forecast()
        
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/forecast"
                params = {
                    'lat': self.lat,
                    'lon': self.lon,
                    'appid': self.api_key,
                    'units': self.units,
                    'cnt': days * 8  # 8 forecasts per day (every 3 hours)
                }
                
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return self._parse_forecast_data(data)
                    else:
                        logger.warning(f"Forecast API returned status {response.status}")
                        return self._get_mock_forecast()
                        
        except Exception as e:
            logger.warning(f"Failed to fetch forecast data: {e}")
            return self._get_mock_forecast()
    
    def _parse_weather_data(self, data: Dict[str, Any]) -> WeatherData:
        """Parse weather API response."""
        weather = data['weather'][0]
        main = data['main']
        wind = data.get('wind', {})
        
        return WeatherData(
            temperature=main['temp'],
            feels_like=main['feels_like'],
            humidity=main['humidity'],
            pressure=main['pressure'],
            description=weather['description'].title(),
            icon=weather['icon'],
            wind_speed=wind.get('speed', 0),
            wind_direction=wind.get('deg', 0),
            visibility=data.get('visibility', 10000) / 1000,  # Convert to km
            uv_index=None,  # Would need separate API call
            location=self.location_name,
            timestamp=datetime.now()
        )
    
    def _parse_forecast_data(self, data: Dict[str, Any]) -> list[ForecastData]:
        """Parse forecast API response."""
        forecasts = []
        daily_data = {}
        
        # Group by day and find min/max temperatures
        for item in data['list']:
            date = datetime.fromtimestamp(item['dt']).date()
            
            if date not in daily_data:
                daily_data[date] = {
                    'temps': [],
                    'descriptions': [],
                    'icons': [],
                    'precipitation': []
                }
            
            daily_data[date]['temps'].append(item['main']['temp'])
            daily_data[date]['descriptions'].append(item['weather'][0]['description'])
            daily_data[date]['icons'].append(item['weather'][0]['icon'])
            
            # Get precipitation chance if available
            pop = item.get('pop', 0) * 100  # Convert to percentage
            daily_data[date]['precipitation'].append(pop)
        
        # Create forecast objects
        for date, day_data in list(daily_data.items())[:5]:  # Limit to 5 days
            forecasts.append(ForecastData(
                date=datetime.combine(date, datetime.min.time()),
                temperature_high=max(day_data['temps']),
                temperature_low=min(day_data['temps']),
                description=max(set(day_data['descriptions']), key=day_data['descriptions'].count).title(),
                icon=max(set(day_data['icons']), key=day_data['icons'].count),
                precipitation_chance=int(max(day_data['precipitation']) if day_data['precipitation'] else 0)
            ))
        
        return forecasts
    
    def _get_mock_weather(self) -> WeatherData:
        """Return mock weather data when API is not available."""
        return WeatherData(
            temperature=72.0,
            feels_like=75.0,
            humidity=65,
            pressure=1013,
            description="Partly Cloudy",
            icon="02d",
            wind_speed=5.2,
            wind_direction=230,
            visibility=10.0,
            uv_index=6.0,
            location=self.location_name,
            timestamp=datetime.now()
        )
    
    def _get_mock_forecast(self) -> list[ForecastData]:
        """Return mock forecast data when API is not available."""
        forecasts = []
        base_date = datetime.now()
        
        mock_data = [
            (75, 58, "Sunny", "01d", 10),
            (73, 55, "Partly Cloudy", "02d", 20),
            (68, 52, "Cloudy", "03d", 40),
            (66, 50, "Light Rain", "10d", 80),
            (70, 53, "Partly Cloudy", "02d", 30)
        ]
        
        for i, (high, low, desc, icon, precip) in enumerate(mock_data):
            forecasts.append(ForecastData(
                date=base_date.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=i),
                temperature_high=high,
                temperature_low=low,
                description=desc,
                icon=icon,
                precipitation_chance=precip
            ))
        
        return forecasts

    async def collect_data(self) -> Dict[str, Any]:
        """Collect weather data for the dashboard."""
        try:
            logger.info("Collecting weather data...")
            
            # Get current weather
            current_weather = await self.get_current_weather()
            
            # Get forecast
            forecast = await self.get_forecast()
            
            if current_weather:
                result = {
                    'temperature': current_weather.temperature,
                    'feels_like': current_weather.feels_like,
                    'humidity': current_weather.humidity,
                    'pressure': current_weather.pressure,
                    'description': current_weather.description,
                    'icon': current_weather.icon,
                    'wind_speed': current_weather.wind_speed,
                    'wind_direction': current_weather.wind_direction,
                    'visibility': current_weather.visibility,
                    'uv_index': current_weather.uv_index,
                    'location': current_weather.location,
                    'timestamp': current_weather.timestamp.isoformat(),
                    'forecast': [
                        {
                            'date': f.date.strftime('%Y-%m-%d'),
                            'high': f.temperature_high,
                            'low': f.temperature_low,
                            'description': f.description,
                            'icon': f.icon,
                            'precipitation_chance': f.precipitation_chance
                        }
                        for f in forecast[:5]  # 5-day forecast
                    ]
                }
                
                # Add API status info
                if not self.api_key or self.api_key == 'your_openweather_api_key':
                    result['api_status'] = 'mock_data'
                    result['setup_note'] = 'Get a free API key from https://openweathermap.org/api and set OPENWEATHER_API_KEY environment variable for real weather data'
                else:
                    result['api_status'] = 'live_data'
                
                logger.info(f"Weather data collected successfully for {current_weather.location}")
                return result
            else:
                logger.warning("Failed to collect weather data")
                return {}
                
        except Exception as e:
            logger.error(f"Error collecting weather data: {e}")
            return {}
