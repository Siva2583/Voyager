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

# STRONGEST CORS: Specifically allow all your Vercel domains
CORS(app, resources={r"/*": {
    "origins": [
        "https://voyager-dgby.vercel.app", 
        "https://voyager-slvc.vercel.app", 
        "https://voyager-ycjf.vercel.app"
    ],
    "methods": ["GET", "POST", "OPTIONS"],
    "allow_headers": ["Content-Type", "Authorization"]
}})

# IMMEDIATE PREFLIGHT HANDLER: Stops the "2-second" crash
@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        res = make_response()
        res.headers.add("Access-Control-Allow-Origin", "*")
        res.headers.add("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        res.headers.add("Access-Control-Allow-Headers", "Content-Type,Authorization")
        return res, 204

API_KEY = os.getenv("GOOGLE_API_KEY")
MODEL_CHAIN = ['gemini-1.5-flash', 'gemini-2.0-flash-001']

def fetch_activity_details(activity, location_context):
    place_name = activity.get('place', 'Unknown')
    activity['image'] = f"https://loremflickr.com/800/600/{place_name.replace(' ', ',')},travel"
    try:
        geolocator = ArcGIS(user_agent="VoyagerAI_App")
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
                response = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=25)
                if response.status_code == 200:
                    raw_text = response.json()['candidates'][0]['content']['parts'][0]['text']
                    trip_data = json.loads(raw_text.strip('`json \n'))
                    
                    acts = [a for d in trip_data.get('itinerary', []) for a in d.get('activities', [])]
                    # Keep workers low (3) so Railway doesn't run out of memory
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
