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
CORS(app, resources={r"/*": {"origins": "*"}})

API_KEY = os.getenv("GOOGLE_API_KEY")

MODEL_CHAIN = [
    'gemini-2.5-flash', 
    'gemini-2.5-pro', 
    'gemini-2.0-flash-001'
]

def fetch_activity_details(activity, location_context):
    place_name = activity.get('place')
    if not place_name: return activity
    image_url = None
    try:
        clean_query = place_name.split('(')[0].strip()
        url = "https://en.wikipedia.org/w/api.php"
        params = {"action": "query", "format": "json", "generator": "search", "gsrsearch": clean_query, "gsrlimit": 1, "prop": "pageimages", "piprop": "thumbnail", "pithumbsize": 800}
        headers = {'User-Agent': 'VoyagerAI/1.0'}
        response = requests.get(url, params=params, headers=headers)
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
            loc = geolocator.geocode(f"{clean_query}, {location_context}")
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
        
        prompt = f"""
        Act as a professional local travel consultant in {location}. 
        Create a COMPLETE {days}-day "everything included" itinerary for {people} people.
        Budget: {budget_tier} ({total_budget} INR).

        STRICT REALISM & CONTENT RULES:
        1. INCLUDE EVERYTHING: Every day MUST include:
           - A specific verified Hotel/Resort for 'Check-in & Rest'.
           - Specific local Restaurants for 'Breakfast', 'Lunch', and 'Dinner'.
           - 2-3 Sightseeing activities.
        2. NEIGHBORHOOD LOCK: Group the hotel, restaurants, and activities in the same area each day to avoid traffic.
        3. REAL PLACES ONLY: Use real, verified hotels and eateries in {location}.
        4. COST ACCURACY: 'cost' must be a realistic estimate PER PERSON (e.g., Special Entry Darshan is ₹300).
        5. LOCAL TIPS: In each 'desc', include a pro-tip like 'Book 3 months early' or 'Order the Ghee Roast'.

        JSON SCHEMA:
        {{
            "trip_name": "Full Experience: {location}",
            "total_budget": "Total calculated cost for {people} travelers",
            "itinerary": [
                {{
                    "day": 1,
                    "activities": [
                        {{ 
                            "id": "unique_id",
                            "time": "08:00 AM", 
                            "place": "Verified Name", 
                            "desc": "Detailed description + local insider tip.", 
                            "cost": 0, 
                            "duration": 60,
                            "priority": "high",
                            "energy": "low",
                            "coords": [0.0, 0.0]
                        }}
                    ]
                }}
            ]
        }}
        """

        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": { 
                "temperature": 0.1, 
                "maxOutputTokens": 8000,
                "response_mime_type": "application/json"
            }
        }

        for model_name in MODEL_CHAIN:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={API_KEY}"
            try:
                response = requests.post(url, headers=headers, json=payload)
                if response.status_code == 200:
                    raw_text = response.json()['candidates'][0]['content']['parts'][0]['text']
                    trip_data = json.loads(raw_text.strip())
                    all_acts = [act for d in trip_data.get('itinerary', []) for act in d.get('activities', [])]
                    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
                        futures = [executor.submit(fetch_activity_details, act, location) for act in all_acts]
                        concurrent.futures.wait(futures)
                    return jsonify(trip_data)
                elif response.status_code == 429: continue
            except: continue
        return jsonify({"error": "Service busy. Try again."}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
