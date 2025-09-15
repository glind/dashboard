import asyncio
from collectors.weather_collector import WeatherCollector

async def test_weather():
    weather = await WeatherCollector().get_current_weather()
    print(weather)

if __name__ == "__main__":
    asyncio.run(test_weather())
