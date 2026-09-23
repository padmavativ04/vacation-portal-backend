import requests
import os
from dotenv import load_dotenv

load_dotenv()

class PlacesFinder:
    def __init__(self):
        self.api_key = os.getenv('GOOGLE_PLACES_KEY')
        self.base_url = 'https://maps.googleapis.com/maps/api/place'
    
    def get_coords(self, city):
        """Get city coordinates"""
        url = f'{self.base_url}/textsearch/json'
        params = {
            'query': city,
            'key': self.api_key
        }
        
        response = requests.get(url, params=params)
        if response.status_code == 200:
            results = response.json().get('results', [])
            if results:
                loc = results[0]['geometry']['location']
                return loc['lat'], loc['lng']
        return None, None
    
    def search_places(self, city, place_type='tourist_attraction'):
        """Find attractions"""
        lat, lng = self.get_coords(city)
        if not lat:
            return []
        
        url = f'{self.base_url}/nearbysearch/json'
        params = {
            'location': f'{lat},{lng}',
            'radius': 15000,
            'type': place_type,
            'key': self.api_key
        }
        
        response = requests.get(url, params=params)
        if response.status_code == 200:
            places = []
            for result in response.json().get('results', [])[:10]:
                places.append({
                    'name': result.get('name'),
                    'rating': result.get('rating', 0),
                    'address': result.get('vicinity'),
                    'type': place_type
                })
            return places
        return []
    
    def search_all(self, city):
        """Find all attraction types"""
        types = ['museum', 'park', 'restaurant', 'tourist_attraction']
        results = {}

        for t in types:
            results[t] = self.search_places(city, t)

        return results

    def search_hotels(self, city):
        """Find hotels (lodging). Note: Places API only exposes price_level (0-4 tier), not a $ amount."""
        lat, lng = self.get_coords(city)
        if not lat:
            return []

        url = f'{self.base_url}/nearbysearch/json'
        params = {
            'location': f'{lat},{lng}',
            'radius': 15000,
            'type': 'lodging',
            'key': self.api_key
        }

        response = requests.get(url, params=params)
        if response.status_code == 200:
            hotels = []
            for result in response.json().get('results', [])[:10]:
                hotels.append({
                    'name': result.get('name'),
                    'rating': result.get('rating', 0),
                    'address': result.get('vicinity'),
                    'price_level': result.get('price_level')
                })
            return hotels
        return []


if __name__ == '__main__':
    finder = PlacesFinder()
    places = finder.search_all('Paris')
    for category, items in places.items():
        print(f"\n{category}:")
        for item in items[:3]:
            print(f"  - {item['name']} ({item['rating']}⭐)")