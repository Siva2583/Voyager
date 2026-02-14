import requests
import json
url = "http://127.0.0.1:4000/api/trip"
payload = {
    "location": "Kurnool",
    "days": 3,
    "budget": 15000,
    "travelers": 2,
    "vibe": ["Eat","Travel","Relax"]
}
try:
    print("GETTING RESPONSE.....")
    response=requests.post(url,json=payload)
    print(json.dumps(response.json(),indent=2))
except Exception as e:
    print(f"\n Error: {e}")
