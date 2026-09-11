import urllib.request
import json
import time

test_routes = [
    ("Delhi", "Jaipur"),
    ("Mumbai", "Pune"),
    ("Bengaluru", "Kochi"),
    ("Chennai", "Hyderabad"),
    ("Kolkata", "Bhubaneswar"),
    ("Srinagar", "Leh"),
    ("Ahmedabad", "Surat"),
    ("Bhopal", "Indore"),
    ("Patna", "Ranchi"),
    ("Nainital", "Bhimtal"),
    ("Guwahati", "Shillong")
]

print("=== TESTING ALL-INDIA ROUTE OPTIMIZATION & WEATHER ===")
for origin, dest in test_routes:
    req = urllib.request.Request(
        "http://127.0.0.1:8002/api/v1/routes/optimize",
        data=json.dumps({"origin": origin, "destination": dest, "goal": "safest"}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    try:
        t0 = time.time()
        with urllib.request.urlopen(req) as res:
            data = json.loads(res.read().decode())
            elapsed = time.time() - t0
            print(f"[OK] {data['origin']} -> {data['destination']}: {data['distance_km']} km | {data['duration_formatted']} | Temp: {data.get('temperature_c')}C | {data.get('weather_condition')} | Points: {len(data.get('route_coordinates', []))} | News: {len(data.get('disaster_news', []))} ({elapsed:.2f}s)")
    except Exception as e:
        print(f"[FAIL] {origin} -> {dest}: {e}")
