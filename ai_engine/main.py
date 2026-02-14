import requests
import time
import json
import os
import concurrent.futures
import google.generativeai as genai
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from geopy.geocoders import ArcGIS 

load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return response

# Ensure this matches your Railway Variable name
API_KEY = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=API_KEY)

MODEL_CHAIN = [
    'gemini-1.5-flash',
    'gemini-1.5-pro'
]

def fetch_activity_details(activity, location_context):
    try:
        place_name = activity.get('place', 'Point of Interest')
        clean_query = place_name.split('(')[0].strip()
        activity['image'] = f"[https://loremflickr.com/800/600/](https://loremflickr.com/800/600/){clean_query.replace(' ', ',')},travel/all"
        try:
            wiki_url = "[https://en.wikipedia.org/w/api.php](https://en.wikipedia.org/w/api.php)"
            params = {"action": "query", "format": "json", "generator": "search", "gsrsearch": clean_query, "gsrlimit": 1, "prop": "pageimages", "piprop": "thumbnail", "pithumbsize": 800}
            res = requests.get(wiki_url, params=params, timeout=1.5)
            pages = res.json().get("query", {}).get("pages", {})
            for _, page_data in pages.items():
                if "thumbnail" in page_data:
                    activity['image'] = page_data["thumbnail"]["source"]
        except: pass
        if not activity.get('coords') or activity['coords'] == [0.0, 0.0]:
            try:
                geolocator = ArcGIS(user_agent="VoyagerAI_v1")
                loc = geolocator.geocode(f"{clean_query}, {location_context}, India", timeout=2)
                activity['coords'] = [loc.latitude, loc.longitude] if loc else [0.0, 0.0]
            except: activity['coords'] = [0.0, 0.0]
    except: pass
    return activity

@app.route('/', methods=['GET'])
def home():
    return "Voyager AI Engine Running", 200

@app.route('/generate', methods=['POST'])
def generate_itinerary():
    try:
        data = request.json
        if not data: return jsonify({"error": "No data"}), 400
        location, days = data.get('location', 'India'), data.get('days', 3)
        people, budget = data.get('people', 1), data.get('total_budget', 'Flexible')
        
        prompt = f"Plan {days} days in {location} for {people} (Budget: {budget}). Return ONLY JSON: {{'trip_name': '', 'total_budget': '', 'itinerary': [{{'day': 1, 'activities': [{{'id': '1', 'time': 'Morning', 'place': '', 'desc': '', 'cost': 0, 'duration': 60, 'priority': 'high', 'energy': 'medium', 'coords': [0,0]}}]}}]}}"
        
        last_error = "Unknown"
        for model_name in MODEL_CHAIN:
            try:
                # Using the SDK prevents the "Expecting value" error entirely
                model = genai.GenerativeModel(
                    model_name,
                    generation_config={"response_mime_type": "application/json"}
                )
                
                response = model.generate_content(prompt)
                
                # The SDK handles the parsing safety for us
                trip_data = json.loads(response.text)
                
                all_acts = [act for day in trip_data.get('itinerary', []) for act in day.get('activities', [])]
                with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                    executor.map(lambda act: fetch_activity_details(act, location), all_acts)
                
                return jsonify(trip_data)
            except Exception as inner_e:
                last_error = str(inner_e)
                continue
                
        return jsonify({"error": f"AI Failure: {last_error}"}), 503
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
