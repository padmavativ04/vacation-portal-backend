import os
import json
from datetime import datetime

from dotenv import load_dotenv
from agents.orchestrator import Orchestrator

load_dotenv()

try:
    import anthropic
except ImportError:
    anthropic = None

MODEL_ID = "claude-opus-4-8"
MAX_TOOL_ITERATIONS = 8

_orchestrator = Orchestrator()

# session_id -> {"messages": [...], "accumulator": {...}}
SESSIONS = {}

SYSTEM_PROMPT = """You are a conversational trip-planning assistant for a vacation portal. \
You help users plan a full trip (flights, hotels, activities, weather, budget) by calling \
tools, and you can answer follow-up questions about a trip you already planned earlier in \
this conversation without re-running everything.

Before calling any tools, gather these details conversationally: origin city, destination \
city, total budget in USD, departure date, return date, and number of adults (default 1 if \
not mentioned). Ask for anything missing rather than guessing. If a date is vague (e.g. \
"sometime in September"), ask the user to confirm a specific YYYY-MM-DD date, or propose one \
and get confirmation.

Once you have all five required details, call tools in this order - later steps depend on \
data from earlier ones:
1. resolve_city_to_iata for the origin city, then for the destination city.
2. search_flights with both airport codes and the two dates.
3. allocate_budget (needs the flight price and trip length from step 2).
4. search_places, get_weather, and search_hotels for the destination city.
5. build_itinerary, once search_places and get_weather have both completed.

For follow-up questions about a trip you already planned (e.g. "what's the weather like \
there?", "any cheaper hotels?", "how much is left for activities?"), answer from the \
conversation history and tool results you already have - do not re-run the pipeline. Only \
call a tool again if the user asks for something you don't already have, or changes the \
destination, dates, or budget.

If a tool returns no results or an error (e.g. no flights found, flight cost exceeds \
budget), tell the user plainly and ask how they'd like to proceed. Never fabricate flight, \
hotel, weather, or price data.

Keep replies concise and conversational - the app renders the full structured trip data \
separately, so you don't need to restate every field a tool returned."""

TOOLS = [
    {
        "name": "resolve_city_to_iata",
        "description": "Resolve a free-text city name (e.g. 'Mumbai', 'new york') to its IATA airport code using an offline lookup. Call this once for the origin city and once for the destination city before searching flights. Returns the airport code, or an error if no match was found.",
        "input_schema": {
            "type": "object",
            "properties": {
                "city_name": {"type": "string", "description": "City name as given by the user, e.g. 'Mumbai' or 'New York'."}
            },
            "required": ["city_name"]
        }
    },
    {
        "name": "search_flights",
        "description": "Search round-trip flights between two airports. Requires IATA airport codes for both endpoints (use resolve_city_to_iata first). Returns up to 5 flight options with price, airline, duration, departure/arrival, and stops.",
        "input_schema": {
            "type": "object",
            "properties": {
                "from_airport": {"type": "string", "description": "Origin IATA airport code, e.g. 'JFK'."},
                "to_airport": {"type": "string", "description": "Destination IATA airport code, e.g. 'CDG'."},
                "depart_date": {"type": "string", "description": "Departure date, format YYYY-MM-DD."},
                "return_date": {"type": "string", "description": "Return date, format YYYY-MM-DD."},
                "adults": {"type": "integer", "description": "Number of adult passengers. Default 1 if the user hasn't specified."}
            },
            "required": ["from_airport", "to_airport", "depart_date", "return_date"]
        }
    },
    {
        "name": "search_places",
        "description": "Find tourist attractions in the destination city, grouped into museum/park/restaurant/tourist_attraction categories.",
        "input_schema": {
            "type": "object",
            "properties": {"city": {"type": "string", "description": "Destination city name, e.g. 'Paris'."}},
            "required": ["city"]
        }
    },
    {
        "name": "search_hotels",
        "description": "Find hotels (lodging) in the destination city. Each result has a 0-4 price tier (price_level) rather than a dollar amount.",
        "input_schema": {
            "type": "object",
            "properties": {"city": {"type": "string", "description": "Destination city name, e.g. 'Paris'."}},
            "required": ["city"]
        }
    },
    {
        "name": "get_weather",
        "description": "Get a short-range weather forecast (roughly the first 2 days, 3-hour resolution) for the destination city.",
        "input_schema": {
            "type": "object",
            "properties": {"city": {"type": "string", "description": "Destination city name, e.g. 'Paris'."}},
            "required": ["city"]
        }
    },
    {
        "name": "allocate_budget",
        "description": "Split the traveler's total budget across flights, hotels, activities, meals, and transport. Call this after search_flights has returned a price. If flight_cost or num_nights are omitted, the most recent search_flights result and dates from this conversation are used automatically.",
        "input_schema": {
            "type": "object",
            "properties": {
                "total_budget": {"type": "number", "description": "Traveler's total budget in USD."},
                "flight_cost": {"type": "string", "description": "Optional. Price of the selected flight, e.g. '$910'. Defaults to the most recent search_flights result if omitted."},
                "num_nights": {"type": "integer", "description": "Optional. Number of nights of the trip. Defaults to the depart/return date difference if omitted."}
            },
            "required": ["total_budget"]
        }
    },
    {
        "name": "build_itinerary",
        "description": "Assemble a day-by-day itinerary sequencing the attractions and weather already found for this trip. Call this only after search_places and get_weather have both been called for the destination in this conversation - it reuses those results automatically.",
        "input_schema": {
            "type": "object",
            "properties": {
                "num_nights": {"type": "integer", "description": "Optional override. Defaults to the trip's computed value."},
                "depart_date": {"type": "string", "description": "Optional override, format YYYY-MM-DD. Defaults to the trip's depart date."}
            },
            "required": []
        }
    },
]


def _handle_resolve_city_to_iata(tool_input, acc):
    from agents.airport_lookup import resolve_city_to_iata
    code = resolve_city_to_iata(tool_input["city_name"])
    if code is None:
        return {"error": f"No airport found for '{tool_input['city_name']}'"}, True
    return {"iata_code": code}, False


def _handle_search_flights(tool_input, acc):
    flights = _orchestrator.flight_searcher.search(
        tool_input["from_airport"], tool_input["to_airport"],
        tool_input["depart_date"], tool_input["return_date"],
        tool_input.get("adults", 1),
    )
    acc["depart_date"] = tool_input["depart_date"]
    acc["return_date"] = tool_input["return_date"]
    acc["num_nights"] = (
        datetime.strptime(tool_input["return_date"], "%Y-%m-%d")
        - datetime.strptime(tool_input["depart_date"], "%Y-%m-%d")
    ).days
    acc["flights"] = flights
    acc["best_flight"] = flights[0] if flights else None
    if not flights:
        return {"flights": [], "note": "No flights found."}, False
    return {"flights": flights}, False


def _handle_search_places(tool_input, acc):
    places = _orchestrator.places_finder.search_all(tool_input["city"])
    acc["places"] = places
    acc["city"] = tool_input["city"]
    return places, False


def _handle_search_hotels(tool_input, acc):
    hotels = _orchestrator.places_finder.search_hotels(tool_input["city"])
    acc["hotels"] = hotels
    acc["city"] = tool_input["city"]
    return {"hotels": hotels}, False


def _handle_get_weather(tool_input, acc):
    weather = _orchestrator.weather_agent.get_weather(tool_input["city"])
    acc["weather"] = weather
    acc["city"] = tool_input["city"]
    return {"weather": weather}, False


def _handle_allocate_budget(tool_input, acc):
    flight_cost = tool_input.get("flight_cost")
    if flight_cost is None:
        best = acc.get("best_flight")
        if not best:
            return {"error": "No flight price available yet - call search_flights first."}, True
        flight_cost = best["price"]
    num_nights = tool_input.get("num_nights", acc.get("num_nights"))
    if num_nights is None:
        return {"error": "num_nights unknown - call search_flights first or provide dates."}, True
    budget = _orchestrator.budget_allocator.allocate(tool_input["total_budget"], flight_cost, num_nights)
    acc["budget"] = budget
    if "error" in budget:
        return budget, True
    return budget, False


def _handle_build_itinerary(tool_input, acc):
    places = acc.get("places")
    weather = acc.get("weather")
    if places is None or weather is None:
        return {"error": "Call search_places and get_weather for the destination first."}, True
    num_nights = tool_input.get("num_nights", acc.get("num_nights"))
    depart_date = tool_input.get("depart_date", acc.get("depart_date"))
    if num_nights is None or depart_date is None:
        return {"error": "num_nights/depart_date unknown - call search_flights first or provide them."}, True
    itinerary = _orchestrator.build_itinerary(places, weather, num_nights, depart_date)
    acc["itinerary"] = itinerary
    return {"itinerary": itinerary}, False


TOOL_DISPATCH = {
    "resolve_city_to_iata": _handle_resolve_city_to_iata,
    "search_flights": _handle_search_flights,
    "search_places": _handle_search_places,
    "search_hotels": _handle_search_hotels,
    "get_weather": _handle_get_weather,
    "allocate_budget": _handle_allocate_budget,
    "build_itinerary": _handle_build_itinerary,
}


def _get_client():
    if anthropic is None:
        raise RuntimeError("The 'anthropic' package is not installed. Run: pip install anthropic")
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set. Add it to your .env file to use the chatbot.")
    return anthropic.Anthropic(api_key=api_key)


def _get_session(session_id):
    if session_id not in SESSIONS:
        SESSIONS[session_id] = {"messages": [], "accumulator": {}}
    return SESSIONS[session_id]


def _assemble_trip(acc):
    required = ["best_flight", "budget", "places", "weather", "hotels", "num_nights", "city", "itinerary"]
    if any(acc.get(k) is None for k in required):
        return None
    if isinstance(acc["budget"], dict) and "error" in acc["budget"]:
        return None
    return {
        "flight": acc["best_flight"],
        "budget": acc["budget"],
        "places": acc["places"],
        "weather": (acc["weather"] or [])[:3],
        "hotels": (acc["hotels"] or [])[:3],
        "num_nights": acc["num_nights"],
        "city": acc["city"],
        "itinerary": acc["itinerary"],
    }


def run_agent_turn(session_id, user_message):
    client = _get_client()
    session = _get_session(session_id)
    messages = session["messages"]
    acc = session["accumulator"]

    messages.append({"role": "user", "content": user_message})

    reply_text = ""
    for _ in range(MAX_TOOL_ITERATIONS):
        response = client.messages.create(
            model=MODEL_ID,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            thinking={"type": "adaptive"},
            messages=messages,
        )

        if response.stop_reason == "refusal":
            reply_text = "I'm not able to help with that request."
            messages.append({"role": "assistant", "content": response.content})
            break

        if response.stop_reason != "tool_use":
            reply_text = next((b.text for b in response.content if b.type == "text"), "")
            messages.append({"role": "assistant", "content": response.content})
            break

        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            handler = TOOL_DISPATCH.get(block.name)
            if handler is None:
                result, is_error = {"error": f"Unknown tool '{block.name}'"}, True
            else:
                try:
                    result, is_error = handler(block.input, acc)
                except Exception as e:
                    result, is_error = {"error": str(e)}, True
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(result, default=str),
                "is_error": is_error,
            })
        messages.append({"role": "user", "content": tool_results})
    else:
        reply_text = reply_text or "I wasn't able to finish that within the allotted steps - could you clarify what you'd like next?"

    trip = _assemble_trip(acc)
    return reply_text, trip
