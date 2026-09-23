import requests
import os
from dotenv import load_dotenv

load_dotenv()

class WeatherAgent:
    def __init__(self):
        self.api_key = os.getenv('OPENWEATHER_KEY')
        self.base_url = 'https://api.openweathermap.org/data/2.5/forecast'
    
    def get_weather(self, city):
        """Get 5-day weather forecast"""
        params = {
            'q': city,
            'appid': self.api_key,
            'units': 'metric'
        }
        
        response = requests.get(self.base_url, params=params)
        if response.status_code == 200:
            data = response.json()
            weather = []
            
            for item in data.get('list', [])[:8]:  # First 2 days
                weather.append({
                    'date': item.get('dt_txt'),
                    'temp': item.get('main', {}).get('temp'),
                    'humidity': item.get('main', {}).get('humidity'),
                    'description': item.get('weather', [{}])[0].get('description'),
                    'rain_chance': item.get('clouds', {}).get('all')
                })
            
            return weather
        return []


if __name__ == '__main__':
    weather = WeatherAgent()
    forecast = weather.get_weather('Paris')
    print("Paris Weather Forecast:")
    for day in forecast[:5]:
        print(f"  {day['date']}: {day['temp']}°C, {day['description']}, {day['humidity']}% humidity")