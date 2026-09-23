import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flight_searcher import FlightSearcher
from places_finder import PlacesFinder
from weather_agent import WeatherAgent
from budget_allocator import BudgetAllocator
from datetime import datetime, timedelta

CITY_NAMES = {
    'Paris': 'Paris, France',
    'CDG': 'Paris, France',
    'NYC': 'New York, USA',
    'JFK': 'New York, USA',
    'London': 'London, UK',
    'LHR': 'London, UK',
    'LAX': 'Los Angeles, USA',
    'SFO': 'San Francisco, USA',
    'Tokyo': 'Tokyo, Japan',
    'NRT': 'Tokyo, Japan'
}

class Orchestrator:
    def __init__(self):
        self.flight_searcher = FlightSearcher()
        self.places_finder = PlacesFinder()
        self.weather_agent = WeatherAgent()
        self.budget_allocator = BudgetAllocator()
    
    def plan_trip(self, from_airport, to_airport, depart_date, return_date, adults, total_budget, to_city_name=None):
        """Main trip planner - coordinates all agents"""
        
        print(f"🔍 Searching flights {from_airport} → {to_airport}...")
        flights = self.flight_searcher.search(from_airport, to_airport, depart_date, return_date, adults)
        
        if not flights:
            return {'error': 'No flights found'}
        
        best_flight = flights[0]
        flight_cost = best_flight['price']
        
        print(f"✈️ Found flight: {flight_cost}")
        
        # Calculate nights
        num_nights = (datetime.strptime(return_date, '%Y-%m-%d') - datetime.strptime(depart_date, '%Y-%m-%d')).days
        
        print(f"💰 Allocating budget...")
        budget = self.budget_allocator.allocate(total_budget, flight_cost, num_nights)
        
        # Get full city name
        city_name = to_city_name or CITY_NAMES.get(to_airport, to_airport)
        
        print(f"🗽 Finding attractions...")
        places = self.places_finder.search_all(city_name)
        
        print(f"🌤️ Getting weather...")
        weather = self.weather_agent.get_weather(city_name)
        
        print(f"🏨 Finding hotels...")
        hotels = self.places_finder.search_hotels(city_name)

        itinerary = self.build_itinerary(places, weather, num_nights, depart_date)

        return {
            'flight': best_flight,
            'budget': budget,
            'places': places,
            'weather': weather[:3] if weather else [],
            'hotels': hotels[:3] if hotels else [],
            'num_nights': num_nights,
            'city': city_name,
            'itinerary': itinerary
        }

    def build_itinerary(self, places, weather, num_nights, depart_date):
        """Sequence found places/weather into a day-by-day plan"""
        all_places = []
        for category, items in places.items():
            for item in items:
                all_places.append({**item, 'category': category})

        num_days = num_nights + 1
        start = datetime.strptime(depart_date, '%Y-%m-%d')
        itinerary = []

        for day_index in range(num_days):
            day_date = start + timedelta(days=day_index)
            itinerary.append({
                'day': day_index + 1,
                'date': day_date.strftime('%Y-%m-%d'),
                'weather': weather[day_index] if weather and day_index < len(weather) else None,
                'activities': all_places[day_index::num_days]
            })

        return itinerary


if __name__ == '__main__':
    try:
        print("Starting orchestrator...\n")
        orchestrator = Orchestrator()
        
        trip = orchestrator.plan_trip('JFK', 'Paris', '2026-09-01', '2026-09-06', 1, 5000)
        
        print("\n=== TRIP SUMMARY ===")
        if 'error' in trip:
            print(f"Error: {trip['error']}")
        else:
            print(f"Destination: {trip['city']}")
            print(f"Flight: {trip['flight']['airline']} - {trip['flight']['price']}")
            print(f"Hotel Budget: ${trip['budget']['max_hotel_per_night']:.2f}/night")
            print(f"Duration: {trip['num_nights']} nights")
            print(f"Hotels found: {len(trip['hotels'])}")
            print(f"Attractions: {sum(len(v) for v in trip['places'].values())} total")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()