import requests
import os
from dotenv import load_dotenv

load_dotenv()

class FlightSearcher:
    def __init__(self):
        self.api_key = os.getenv('RAPID_API_KEY')
        self.api_host = 'skyscanner-flights4.p.rapidapi.com'
        self.base_url = 'https://skyscanner-flights4.p.rapidapi.com/api/v1/roundtrip'
    
    def search(self, from_airport, to_airport, depart_date, return_date, adults=1):
        """Search flights"""
        
        params = {
            'origin': from_airport,
            'destination': to_airport,
            'date': depart_date,
            'return_date': return_date,
            'limit': 10,
            'adults': adults,
            'cabin': 'economy',
            'currency': 'USD'
        }
        
        headers = {
            'x-rapidapi-host': self.api_host,
            'x-rapidapi-key': self.api_key
        }
        
        try:
            response = requests.get(self.base_url, params=params, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                flights = []
                
                for result in data.get('results', [])[:5]:
                    flight = {
                        'price': result.get('price'),
                        'airline': result.get('carriers', ['Unknown'])[0],
                        'duration_mins': result.get('legs', [{}])[0].get('dur_min', 0),
                        'departure': result.get('legs', [{}])[0].get('dep', 'N/A'),
                        'arrival': result.get('legs', [{}])[0].get('arr', 'N/A'),
                        'stops': result.get('legs', [{}])[0].get('stops', 0)
                    }
                    flights.append(flight)
                
                return flights
        except Exception as e:
            print(f"Error: {e}")
        
        return []


if __name__ == '__main__':
    searcher = FlightSearcher()
    flights = searcher.search('JFK', 'LHR', '2026-08-17', '2026-08-24', 1)
    print(f"Found {len(flights)} flights")
    for f in flights:
        print(f)