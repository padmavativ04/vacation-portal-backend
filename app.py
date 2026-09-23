import uuid
from flask import Flask, request, jsonify
from flask_cors import CORS
from agents.orchestrator import Orchestrator
from agents.airport_lookup import resolve_city_to_iata
from agents.chat_agent import run_agent_turn

app = Flask(__name__)
CORS(app)

orchestrator = Orchestrator()

REQUIRED_FIELDS = ['from_city', 'to_city', 'depart_date', 'return_date', 'budget']


@app.route('/', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'message': 'Vacation Portal API running'})


@app.route('/chat', methods=['POST'])
def chat():
    """Main trip-planning endpoint"""
    try:
        data = request.json or {}

        missing = [f for f in REQUIRED_FIELDS if not data.get(f)]
        if missing:
            return jsonify({'error': f'Missing required fields: {", ".join(missing)}'}), 400

        from_city = data['from_city'].strip()
        to_city = data['to_city'].strip()

        from_airport = resolve_city_to_iata(from_city)
        if not from_airport:
            return jsonify({'error': f'Could not resolve origin city "{from_city}" to an airport'}), 400

        to_airport = resolve_city_to_iata(to_city)
        if not to_airport:
            return jsonify({'error': f'Could not resolve destination city "{to_city}" to an airport'}), 400

        trip = orchestrator.plan_trip(
            from_airport,
            to_airport,
            data['depart_date'],
            data['return_date'],
            data.get('adults', 1),
            data['budget'],
            to_city_name=to_city
        )

        if 'error' in trip:
            return jsonify({'error': trip['error']}), 400

        return jsonify(trip)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/agent/chat', methods=['POST'])
def agent_chat():
    """Conversational trip-planning endpoint (LLM tool-calling agent)"""
    try:
        data = request.json or {}
        message = (data.get('message') or '').strip()
        if not message:
            return jsonify({'error': 'message is required'}), 400
        session_id = data.get('session_id') or str(uuid.uuid4())
        reply, trip = run_agent_turn(session_id, message)
        return jsonify({'session_id': session_id, 'reply': reply, 'trip': trip})
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 503
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)