import airportsdata

_AIRPORTS = airportsdata.load('IATA')  # loaded once at import time


def resolve_city_to_iata(city_name):
    """Resolve free-text city name to an IATA code via offline airportsdata lookup.
    Case-insensitive exact match, falling back to prefix then substring match.
    Multi-airport cities (Paris = CDG/ORY/LBG) resolve to the alphabetically-first
    matching code — accepted MVP limitation. Returns None if no match."""
    if not city_name or not city_name.strip():
        return None

    query = city_name.strip().lower()
    candidates = [rec for rec in _AIRPORTS.values() if rec.get('iata') and rec.get('city')]

    for match_fn in (
        lambda rec: rec['city'].strip().lower() == query,
        lambda rec: rec['city'].strip().lower().startswith(query),
        lambda rec: query in rec['city'].strip().lower(),
    ):
        matches = sorted((rec for rec in candidates if match_fn(rec)), key=lambda r: r['iata'])
        if matches:
            return matches[0]['iata']

    return None
