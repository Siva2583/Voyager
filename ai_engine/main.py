import os
import json
import requests
import concurrent.futures
from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
from dotenv import load_dotenv
from geopy.geocoders import ArcGIS

load_dotenv()

app = Flask(__name__)

# Fixed CORS: Use a wildcard for testing to eliminate origin issues
CORS(app, resources={r"/*": {"origins": "*"}})

API_KEY = os.getenv("GOOGLE_API_KEY")
MODEL_CHAIN = ['gemini-1.5-flash', 'gemini-2.0-flash-001']

# IMMEDIATE PREFLIGHT RESPONSE: This stops the 20-second CORS crash
@app.route('/generate', methods=['OPTIONS'])
def handle_options():
    res = make_response()
    res.headers["Access-Control-Allow-Origin"] = "*"
    res.headers["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
    res.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return res, 204

def fetch_activity_details(activity, location_context):
    place_name = activity.get('place')
    if not place_name: return activity
    # Fast placeholder to prevent worker hang
    activity['image'] = f"https://loremflickr.com/800/600/{place_name.replace(' ', ',')},travel"
    try:
        geolocator = ArcGIS(user_agent="Voyager_App")
        # Tight 3s timeout: If geocoding is slow, move on
        loc = geolocator.geocode(f"{place_name}, {location_context}", timeout=3)
        activity['coords'] = [loc.latitude, loc.longitude] if loc else [0.0, 0.0]
    except:
        activity['coords'] = [0.0, 0.0]
    return activity

@app.route('/generate', methods=['POST'])
def generate_itinerary():
    try:
        data = request.json
        location = data.get('location')
        prompt = f"Plan a trip to {location}. Return ONLY JSON."

        for model in MODEL_CHAIN:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={API_KEY}"
            try:
                # Use a session for faster connection reuse
                with requests.Session() as s:
                    response = s.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=25)
                    if response.status_code == 200:
                        raw_data = response.json()['candidates'][0]['content']['parts'][0]['text']
                        trip_data = json.loads(raw_data.strip('`json \n'))
                        
                        acts = [a for d in trip_data.get('itinerary', []) for a in d.get('activities', [])]
                        # Use fewer workers (3) to avoid overloading Railway CPU/RAM
                        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                            executor.map(lambda a: fetch_activity_details(a, location), acts)
                        
                        return jsonify(trip_data)
            except:
                continue
        
        return jsonify({"error": "Service busy"}), 503
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
