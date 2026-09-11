import httpx

routes = [
    ("Delhi", "Jaipur"),
    ("Mumbai", "Pune"),
    ("Bengaluru", "Kochi"),
    ("Chennai", "Hyderabad"),
    ("Kolkata", "Bhubaneswar"),
    ("Srinagar", "Leh"),
    ("Ahmedabad", "Surat"),
    ("Bhopal", "Indore")
]

print("=== ALL INDIA ROUTE VERIFICATION ===")
client = httpx.Client(timeout=30.0)
for o, d in routes:
    r = client.post("http://127.0.0.1:8002/api/v1/routes/optimize", json={"origin": o, "destination": d})
    data = r.json()
    print(f"{data['origin']} -> {data['destination']}: {data['distance_km']} km | {data['duration_formatted']} | Temp: {data.get('temperature_c')}C | {data.get('weather_condition')} | Points: {len(data.get('route_coordinates', []))} | News: {len(data.get('disaster_news', []))}")
