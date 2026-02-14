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

    # 1. Get Image
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

    # 2. Get Coords
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
        
        # --- FIX: Capture the exact total budget number ---
        total_budget = data.get('total_budget', 'Flexible') 

        budget_instruction = ""
        if budget_tier == "Luxury":
            budget_instruction = "Select premium 5-star hotels, fine dining, private transport, and exclusive experiences."
        elif budget_tier == "Budget":
            budget_instruction = "Select hostels, street food/affordable cafes, public transport, and free/cheap attractions. Keep costs strictly low."
        else:
            budget_instruction = "Select balanced 3-4 star hotels, good local restaurants, and mix of paid/free activities."

        # --- FIX: Updated Prompt with strict budget math instructions ---
        prompt = f"""
        Act as a travel planner creating a {budget_tier.upper()} class trip.
        Destination: {location} | Duration: {days} Days | Travelers: {people}
        Vibe: {vibe}

        TOTAL TRIP BUDGET: {total_budget} INR.
        IMPORTANT: This budget is for the ENTIRE GROUP of {people} people combined. 
        Do NOT assume this is per person. The sum of all activity costs multiplied by {people} should ideally stay under {total_budget}.

        STRICT BUDGET RULE: {budget_instruction}

        CRITICAL DATA RULES:
        1. **id**: Unique string.
        2. **duration**: Time in MINUTES.
        3. **priority**: "high", "medium", "low".
        4. **energy**: "high", "medium", "low".
        5. **cost**: Estimated cost for this activity PER PERSON in INR.
        6. **coords**: [Latitude, Longitude] or [0,0].

        JSON SCHEMA:
        {{
            "trip_name": "Creative Trip Title",
            "total_budget": "Estimated Total Cost for Group",
            "itinerary": [
                {{
                    "day": 1,
                    "activities": [
                        {{ 
                            "id": "act_1",
                            "time": "Morning", 
                            "place": "Name", 
                            "desc": "Short description", 
                            "cost": 0, 
                            "duration": 60,
                            "priority": "high",
                            "energy": "medium",
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
            "generationConfig": { "temperature": 0.4, "maxOutputTokens": 8000 }
        }

        for model_name in MODEL_CHAIN:
            print(f"Trying model: {model_name}...")
            url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={API_KEY}"
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=30)
                if response.status_code == 200:
                    clean_text = response.json()['candidates'][0]['content']['parts'][0]['text'].replace("```json", "").replace("```", "").strip()
                    trip_data = json.loads(clean_text)
                    
                    all_activities = []
                    if "itinerary" in trip_data:
                        for day in trip_data['itinerary']:
                            for activity in day.get('activities', []):
                                all_activities.append(activity)
                    
                    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                        futures = [executor.submit(fetch_activity_details, act, location) for act in all_activities]
                        concurrent.futures.wait(futures)

                    return jsonify(trip_data)
                elif response.status_code == 429:
                    continue
            except Exception:
                continue

        return jsonify({"error": "Busy. Try again."}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
