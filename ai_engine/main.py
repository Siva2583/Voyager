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

if not API_KEY:
    print("WARNING: No API Key found in Railway Variables")

MODEL_CHAIN = [
    'models/gemini-2.0-flash-lite-preview-02-05', 
    'models/gemini-flash-latest',               
    'models/gemini-2.5-flash-lite',               
    'models/gemini-2.0-flash',                   
    'models/gemini-exp-1206',                    
    'models/gemini-pro-latest'                   
]

def fetch_activity_details(activity, location_context):
    place_name = activity.get('place')
    if not place_name:
        return activity

    image_url = None
    try:
        clean_query = place_name.split('(')[0].strip()
        url = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrsearch": clean_query,
            "gsrlimit": 1,
            "prop": "pageimages",
            "piprop": "thumbnail",
            "pithumbsize": 800
        }
        headers = {'User-Agent': 'VoyagerAI/1.0'}
        response = requests.get(url, params=params, headers=headers, timeout=2)
        data = response.json()
        pages = data.get("query", {}).get("pages", {})
        for _, page_data in pages.items():
            if "thumbnail" in page_data:
                image_url = page_data["thumbnail"]["source"]
    except Exception:
        pass

    if not image_url:
        image_url = f"https://loremflickr.com/800/600/{clean_query.replace(' ', ',')},travel/all"
    
    activity['image'] = image_url

    try:
        if 'coords' not in activity or activity['coords'] == [0.0, 0.0]:
            geolocator = ArcGIS(user_agent="VoyagerAI_App")
            search_query = f"{clean_query}, {location_context}"
            try:
                loc = geolocator.geocode(search_query, timeout=3)
                if loc:
                    activity['coords'] = [loc.latitude, loc.longitude]
                else:
                    loc = geolocator.geocode(clean_query, timeout=3)
                    if loc:
                        activity['coords'] = [loc.latitude, loc.longitude]
            except Exception:
                pass
    except Exception:
        if 'coords' not in activity:
            activity['coords'] = [0.0, 0.0]

    return activity

@app.route('/', methods=['GET'])
def home():
    return "Voyager AI Engine Running", 200

@app.route('/generate', methods=['POST'])
def generate_itinerary():
    try:
        data = request.json
        location = data.get('location')
        days = data.get('days')
        budget_tier = data.get('budget_tier', 'Medium') 
        people = data.get('people', 1)
        vibe = ", ".join(data.get('vibe', []))
        total_budget = data.get('total_budget', 'Flexible') 

        budget_instruction = ""
        if budget_tier == "Luxury":
            budget_instruction = "Focus on premium 5-star experiences, private chauffeurs, and high-end dining."
        elif budget_tier == "Budget":
            budget_instruction = "Focus on affordable street food, hostels, and public transport. Keep individual activity costs minimal."
        else:
            budget_instruction = "Balanced mix of comfortable hotels and standard local dining."

        # REALISTIC PROMPT: Strict location lock and logic-first generation
        prompt = f"""
        Act as a professional, hyper-local travel consultant for {location}.
        
        STRICT COMMAND: Your output must be 100% specific to {location}. 
        If you suggest a place that is not physically within or immediately adjacent to {location}, the itinerary is considered a failure. 
        Example: If location is Tirupati, do NOT mention Goa, beaches in North India, or unrelated monuments.

        TRIP SPECIFICATIONS:
        - Target City: {location}
        - Duration: {days} Days
        - Group Size: {people} People
        - Style: {vibe}
        - Total Budget for Group: {total_budget} INR
        - Class: {budget_tier} ({budget_instruction})

        EXECUTION RULES:
        1. Only include REAL, verified landmarks and establishments in {location}.
        2. Ensure the "cost" field is a realistic PER PERSON estimate in INR for that specific activity.
        3. All "coords" must be accurate [lat, lng] for the specific spots in {location}.
        4. "total_budget" in the JSON must reflect the actual sum of all activities for {people} people.

        OUTPUT FORMAT: Return ONLY a clean JSON object. No conversational text.
        JSON SCHEMA:
        {{
            "trip_name": "A professional title for a {days}-day trip to {location}",
            "total_budget": "Calculated total for {people} people",
            "itinerary": [
                {{
                    "day": 1,
                    "activities": [
                        {{ 
                            "id": "unique_id",
                            "time": "e.g. 09:00 AM", 
                            "place": "Exact Name", 
                            "desc": "2-sentence detailed insight including local tips", 
                            "cost": 0, 
                            "duration": 90,
                            "priority": "high",
                            "energy": "medium",
                            "coords": [lat, lng]
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
                "temperature": 0.1, # Lowest temperature for maximum factual accuracy
                "maxOutputTokens": 8000,
                "response_mime_type": "application/json"
            }
        }

        for model_name in MODEL_CHAIN:
            print(f"Executing with model: {model_name}...")
            url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={API_KEY}"
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=40)
                if response.status_code == 200:
                    raw_text = response.json()['candidates'][0]['content']['parts'][0]['text']
                    trip_data = json.loads(raw_text.strip())
                    
                    all_activities = []
                    if "itinerary" in trip_data:
                        for day in trip_data['itinerary']:
                            for activity in day.get('activities', []):
                                all_activities.append(activity)
                    
                    # Fetching images and verifying coords via ArcGIS
                    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                        futures = [executor.submit(fetch_activity_details, act, location) for act in all_activities]
                        concurrent.futures.wait(futures)

                    return jsonify(trip_data)
                elif response.status_code == 429:
                    continue
            except Exception:
                continue

        return jsonify({"error": "Engine Timeout. Please retry."}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
