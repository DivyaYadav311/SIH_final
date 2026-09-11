"""
Pulls real terrain data for each location:
  1. Elevation (metres) - from Open-Meteo's free Elevation API (no key needed)
  2. Distance to nearest river/waterway (km) - from OpenStreetMap's Overpass API
     (free, no key needed - it's the same map data that powers OpenStreetMap.org)

Neither of these needs Bhuvan/ISRO registration. If the team later gets a Bhuvan
access token, this file is the place to swap in Bhuvan's terrain data instead -
the output shape (elevation_m, river_proximity_km) should stay the same so
flood_score.py doesn't need to change.

Output: writes data/terrain_raw.json
"""

import json
import math
from pathlib import Path

import requests

from fetch_rainfall import SAMPLE_LOCATIONS  # reuse the same placeholder locations

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

ELEVATION_URL = "https://api.open-meteo.com/v1/elevation"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# How far out to search for a river before giving up and calling it "far"
RIVER_SEARCH_RADIUS_M = 20000  # 20 km
RIVER_NOT_FOUND_KM = 25.0      # fallback value if nothing found in the search radius


def fetch_elevation(lat: float, lon: float) -> float | None:
    """Real elevation in metres for one point, via Open-Meteo."""
    params = {"latitude": lat, "longitude": lon}
    resp = requests.get(ELEVATION_URL, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    elevations = data.get("elevation", [])
    return elevations[0] if elevations else None


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    """Straight-line distance between two lat/lon points, in km."""
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def fetch_nearest_river_km(lat: float, lon: float) -> float:
    """
    Finds the approximate distance (km) to the nearest mapped waterway using
    OpenStreetMap's Overpass API. This is an approximation (uses each matched
    way's rough center, not its exact nearest point) - good enough for a
    risk-scoring heuristic, not survey-grade.
    """
    query = f"""
    [out:json][timeout:25];
    (
      way["waterway"](around:{RIVER_SEARCH_RADIUS_M},{lat},{lon});
    );
    out center;
    """

    headers = {
        "User-Agent": "NER-Smart-Logistics/1.0"
    }

    resp = requests.post(
        OVERPASS_URL,
        data={"data": query},
        headers=headers,
        timeout=30
    )

    resp.raise_for_status()
    elements = resp.json().get("elements", [])

    if not elements:
        return RIVER_NOT_FOUND_KM

    distances = []

    for el in elements:
        center = el.get("center")
        if center:
            distances.append(
                haversine_km(
                    lat,
                    lon,
                    center["lat"],
                    center["lon"]
                )
            )

    return round(min(distances), 2) if distances else RIVER_NOT_FOUND_KM


def fetch_all(locations: list[dict]) -> list[dict]:
    results = []
    for loc in locations:
        try:
            elevation = fetch_elevation(loc["lat"], loc["lon"])
            river_km = fetch_nearest_river_km(loc["lat"], loc["lon"])
            results.append(
                {
                    "segment_id": loc["segment_id"],
                    "name": loc["name"],
                    "elevation_m": elevation,
                    "river_proximity_km": river_km,
                }
            )
            print(f"  {loc['name']}: elevation={elevation}m, nearest river={river_km}km")
        except requests.RequestException as e:
            print(f"  FAILED to fetch terrain for {loc['name']}: {e}")
    return results


def main():
    print("Fetching terrain data (elevation + river proximity)...")
    data = fetch_all(SAMPLE_LOCATIONS)

    out_path = DATA_DIR / "terrain_raw.json"
    with open(out_path, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Saved {len(data)} locations to {out_path}")


if __name__ == "__main__":
    main()
