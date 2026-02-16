import requests
import json
import os
import concurrent.futures
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from geopy.geocoders import ArcGIS 

load_dotenv()

app = Flask(__name__)
# Explicitly allowing all origins to fix CORS issues during timeouts
CORS(app, resources={r"/*": {"origins": "*"}})

API_KEY = os.getenv("GOOGLE_API_KEY")

# Using 1.5-flash as the primary for speed to stay under Vercel's 60s limit
MODEL_CHAIN = [
    'gemini-1.5-flash', 
    'gemini-2.0-flash-001',
    'gemini-2.5-flash'
]

session = requests.Session()

def fetch_activity_details(activity, location_context):
    place_name = activity.get('place')
    if not place_name: return activity
    
    # Quick image fallback to save time
    activity['image'] = f"https://loremflickr.com/800/600/{place_name.replace(' ', ',')},travel/all"
    
    try:
        clean_query = place_name.split('(')[0].strip()
        url = "https://en.wikipedia.org/w/api.php"
        params = {"action": "query", "format": "json", "generator": "search", "gsrsearch": clean_query, "gsrlimit": 1, "prop": "pageimages", "piprop": "thumbnail", "pithumbsize": 800}
        headers = {'User-Agent': 'VoyagerAI/1.0'}
        # Strict 3s timeout per image to avoid overall request hang
        response = session.get(url, params=params, headers=headers, timeout=3)
        data = response.json()
        pages = data.get("query", {}).get("pages", {})
        for _, page_data in pages.items():
            if "thumbnail" in page_data:
                activity['image'] = page_data["thumbnail"]["source"]
    except: pass

    try:
        geolocator = ArcGIS(user_agent="VoyagerAI_App")
        # Strict 3s timeout for geocoding
        loc = geolocator.geocode(f"{clean_query}, {location_context}", timeout=3)
        activity['coords'] = [loc.latitude, loc.longitude] if loc else [0.0, 0.0]
    except:
        activity['coords'] = [0.0, 0.0]
        
    return activity

@app.route('/', methods=['GET'])
def home():
    return "Voyager AI Engine Running", 200

@app.route('/generate', methods=['POST'])
def generate_itinerary():
    try:
        data = request.json
        location, days = data.get('location'), data.get('days')
        people = data.get('people', 1)
        total_budget = data.get('total_budget', 'Flexible')

        prompt = f"Plan {days} days in {location} for {people} people. Total budget {total_budget} INR. Include hotels, specific restaurants, and sights. JSON only."

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": { "temperature": 0.1, "response_mime_type": "application/json" }
        }

        for model_name in MODEL_CHAIN:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={API_KEY}"
            try:
                # 45-second timeout to return a response BEFORE Vercel cuts us off
                response = session.post(url, json=payload, timeout=45)
                if response.status_code == 200:
                    raw_text = response.json()['candidates'][0]['content']['parts'][0]['text']
                    trip_data = json.loads(raw_text.strip())
                    
                    # Parallelizing with strict max_workers to save Railway RAM
                    all_acts = [act for d in trip_data.get('itinerary', []) for act in d.get('activities', [])]
                    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                        futures = [executor.submit(fetch_activity_details, act, location) for act in all_acts]
                        concurrent.futures.wait(futures, timeout=10) # Don't wait more than 10s for images
                        
                    return jsonify(trip_data)
            except requests.exceptions.Timeout:
                continue # Try next model if one hangs
            except: continue
        
        return jsonify({"error": "AI response too slow for Vercel Hobby plan. Try a shorter trip."}), 504
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Using the name guard to prevent Gunicorn worker loops
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
