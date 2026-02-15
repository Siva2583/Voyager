import requests
import time
import json
import os
import concurrent.futures
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from geopy.geocoders import ArcGIS 

load_dotenv()

app = Flask(__name__)
CORS(app)

API_KEY = os.getenv("GOOGLE_API_KEY")

MODEL_CHAIN = [
    'gemini-2.5-flash', 
    'gemini-2.0-flash-001',
    'gemini-1.5-flash'
]

# Use a session to reuse connections (saves RAM)
session = requests.Session()

def fetch_activity_details(activity, location_context):
    place_name = activity.get('place')
    if not place_name: return activity
    image_url = None
    try:
        clean_query = place_name.split('(')[0].strip()
        url = "https://en.wikipedia.org/w/api.php"
        params = {"action": "query", "format": "json", "generator": "search", "gsrsearch": clean_query, "gsrlimit": 1, "prop": "pageimages", "piprop": "thumbnail", "pithumbsize": 800}
        # Fixed timeout to prevent hanging the whole worker
        response = session.get(url, params=params, timeout=5)
        data = response.json()
        pages = data.get("query", {}).get("pages", {})
        for _, page_data in pages.items():
            if "thumbnail" in page_data:
                image_url = page_data["thumbnail"]["source"]
    except: pass
    if not image_url:
        image_url = f"https://loremflickr.com/800/600/{clean_query.replace(' ', ',')},travel/all"
    activity['image'] = image_url
    try:
        if 'coords' not in activity or activity['coords'] == [0.0, 0.0]:
            geolocator = ArcGIS(user_agent="VoyagerAI_App")
            loc = geolocator.geocode(f"{clean_query}, {location_context}", timeout=5)
            activity['coords'] = [loc.latitude, loc.longitude] if loc else [0.0, 0.0]
    except:
        if 'coords' not in activity: activity['coords'] = [0.0, 0.0]
    return activity

@app.route('/', methods=['GET'])
def home():
    return "Voyager AI Engine Running", 200

@app.route('/generate', methods=['POST'])
def generate_itinerary():
    try:
        data = request.json
        location, days = data.get('location'), data.get('days')
        people, vibe = data.get('people', 1), ", ".join(data.get('vibe', []))
        budget_tier, total_budget = data.get('budget_tier', 'Medium'), data.get('total_budget', 'Flexible')

        prompt = f"Professional travel plan for {location}. {days} days, {people} people, {total_budget} budget. Include specific hotels, meals, and sights. JSON only."

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": { "temperature": 0.1, "response_mime_type": "application/json" }
        }

        for model_name in MODEL_CHAIN:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={API_KEY}"
            try:
                response = session.post(url, json=payload, timeout=60)
                if response.status_code == 200:
                    raw_text = response.json()['candidates'][0]['content']['parts'][0]['text']
                    trip_data = json.loads(raw_text.strip())
                    all_acts = [act for d in trip_data.get('itinerary', []) for act in d.get('activities', [])]
                    
                    # LIMIT parallel workers to 5 to avoid crashing the Free Tier CPU
                    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                        futures = [executor.submit(fetch_activity_details, act, location) for act in all_acts]
                        concurrent.futures.wait(futures)
                    return jsonify(trip_data)
            except: continue
        
        return jsonify({"error": "AI overloaded"}), 503
    except Exception as e:
        # Crucial: Send error back so React doesn't show a blank screen
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
