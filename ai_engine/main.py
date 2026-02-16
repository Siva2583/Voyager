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
# Explicitly allowing your Vercel frontend origins
CORS(app, resources={r"/*": {"origins": ["https://voyager-slvc.vercel.app", "https://voyager-dgby.vercel.app", "https://voyager-ycjf.vercel.app"]}})

API_KEY = os.getenv("GOOGLE_API_KEY")
MODEL_CHAIN = ['gemini-1.5-flash', 'gemini-2.0-flash-001']

# MANUALLY HANDLE PREFLIGHT: This stops the CORS error in your screenshot
@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        res = make_response()
        res.headers.add("Access-Control-Allow-Origin", request.headers.get("Origin", "*"))
        res.headers.add("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        res.headers.add("Access-Control-Allow-Headers", "Content-Type,Authorization")
        return res, 204

def fetch_activity_details(activity, location_context):
    place_name = activity.get('place')
    if not place_name: return activity
    # Use a faster placeholder if external APIs are slow
    activity['image'] = f"https://loremflickr.com/800/600/{place_name.replace(' ', ',')},travel"
    try:
        geolocator = ArcGIS(user_agent="Voyager_App")
        loc = geolocator.geocode(f"{place_name}, {location_context}", timeout=5)
        activity['coords'] = [loc.latitude, loc.longitude] if loc else [0.0, 0.0]
    except:
        activity['coords'] = [0.0, 0.0]
    return activity

@app.route('/generate', methods=['POST'])
def generate_itinerary():
    try:
        data = request.json
        location = data.get('location')
        prompt = f"Create a detailed JSON travel itinerary for {location}. Include real hotels and restaurants. Return ONLY JSON."

        for model in MODEL_CHAIN:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={API_KEY}"
            try:
                # 45-second timeout ensures we respond before Vercel kills us
                response = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=45)
                if response.status_code == 200:
                    raw_data = response.json()['candidates'][0]['content']['parts'][0]['text']
                    trip_data = json.loads(raw_data.strip('`json \n'))
                    
                    # Parallel fetching with limited workers to save RAM
                    acts = [a for d in trip_data.get('itinerary', []) for a in d.get('activities', [])]
                    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                        executor.map(lambda a: fetch_activity_details(a, location), acts)
                    
                    return jsonify(trip_data)
            except:
                continue
        
        return jsonify({"error": "AI response took too long for the free plan."}), 504
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
