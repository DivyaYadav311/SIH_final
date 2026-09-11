"""
Pulls rainfall data (past + forecast) from Open-Meteo for a set of NER locations.

Open-Meteo requires no API key. Docs: https://open-meteo.com/en/docs

Output: writes data/rainfall_raw.json — one entry per segment_id with daily
precipitation for the past 30 days and next 7 days.

NOTE: `SAMPLE_LOCATIONS` below is a placeholder. Once the team finalizes the real
segment_id / district list (see "Open items" in docs/api-contracts.md), replace this
with the shared list — ideally imported from shared/constants/ once that exists.
"""

import json
import os
from pathlib import Path

import requests

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# Placeholder locations — swap for the team's agreed segment_id list.
SAMPLE_LOCATIONS = [
    {"segment_id": "NER-D-001", "name": "Guwahati", "lat": 26.1445, "lon": 91.7362},
    {"segment_id": "NER-D-002", "name": "Shillong", "lat": 25.5788, "lon": 91.8933},
    {"segment_id": "NER-D-003", "name": "Imphal", "lat": 24.8170, "lon": 93.9368},
    {"segment_id": "NER-D-004", "name": "Agartala", "lat": 23.8315, "lon": 91.2868},
    {"segment_id": "NER-D-005", "name": "Itanagar", "lat": 27.0844, "lon": 93.6053},
]


def fetch_rainfall_for_location(lat: float, lon: float) -> dict:
    """Fetch past 30 days + next 7 days daily precipitation for one lat/lon."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "precipitation_sum",
        "past_days": 30,
        "forecast_days": 7,
        "timezone": "Asia/Kolkata",
    }
    response = requests.get(OPEN_METEO_URL, params=params, timeout=15)
    response.raise_for_status()
    return response.json()


def fetch_all(locations: list[dict]) -> list[dict]:
    results = []
    for loc in locations:
        try:
            raw = fetch_rainfall_for_location(loc["lat"], loc["lon"])
            daily = raw.get("daily", {})
            results.append(
                {
                    "segment_id": loc["segment_id"],
                    "name": loc["name"],
                    "lat": loc["lat"],
                    "lon": loc["lon"],
                    "dates": daily.get("time", []),
                    "precipitation_mm": daily.get("precipitation_sum", []),
                    "past_days": 30,
                    "forecast_days": 7,
                }
            )
            print(f"  fetched rainfall for {loc['name']} ({loc['segment_id']})")
        except requests.RequestException as e:
            print(f"  FAILED to fetch {loc['name']}: {e}")
    return results


def main():
    print("Fetching rainfall data from Open-Meteo...")
    data = fetch_all(SAMPLE_LOCATIONS)

    out_path = DATA_DIR / "rainfall_raw.json"
    with open(out_path, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Saved {len(data)} locations to {out_path}")


if __name__ == "__main__":
    main()
