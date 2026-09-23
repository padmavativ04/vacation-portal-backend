import requests
import os
from dotenv import load_dotenv
import json

load_dotenv()

api_key = os.getenv('RAPID_API_KEY')
headers = {
    'Content-Type': 'application/json',
    'x-rapidapi-host': 'skyscanner-flights4.p.rapidapi.com',
    'x-rapidapi-key': api_key
}

params = {
    'origin': 'JFK',
    'destination': 'LHR',
    'date': '2026-08-17',
    'return_date': '2026-08-24',
    'limit': 5,
    'adults': 1,
    'cabin': 'economy',
    'currency': 'USD'
}

response = requests.get(
    'https://skyscanner-flights4.p.rapidapi.com/api/v1/roundtrip',
    params=params,
    headers=headers
)

print(f"Status: {response.status_code}")
print(f"Full response:\n{json.dumps(response.json(), indent=2)}")
