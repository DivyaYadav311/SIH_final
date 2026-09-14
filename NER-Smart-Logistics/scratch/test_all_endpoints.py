import sys
from pathlib import Path
from fastapi.testclient import TestClient

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

from server.unified_server import app

client = TestClient(app)

endpoints = [
    ("GET", "/health", None),
    ("POST", "/api/v1/predictions/flood", {"latitude": 26.14, "longitude": 91.73}),
    ("POST", "/api/v1/predictions/landslide", {"latitude": 26.14, "longitude": 91.73}),
    ("POST", "/api/v1/road-risk/predict", {"road_id": "NH-27", "flood_probability": 0.3, "landslide_probability": 0.4}),
    ("GET", "/api/v1/warehouses", None),
    ("GET", "/api/v1/shipments", None),
    ("GET", "/api/v1/control-tower/overview", None),
    ("POST", "/api/v1/simulation/what-if", {
        "disrupted_roads": ["NH-27"],
        "severity": 0.8,
        "affected_warehouses": ["WH-GUW-01"],
        "simulate_demand_surge": True,
        "demand_multiplier": 1.5
    }),
]

print("--- TESTING ENDPOINTS ---")
for method, path, payload in endpoints:
    try:
        if method == "GET":
            res = client.get(path)
        else:
            res = client.post(path, json=payload)
        print(f"[{res.status_code}] {method} {path}")
        if res.status_code >= 400:
            print("  Error:", res.text[:200])
    except Exception as e:
        print(f"[EXC] {method} {path} -> {e}")
