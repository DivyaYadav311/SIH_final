"""Build an India susceptibility-training CSV from the public GSI inventory.

The GSI file contains landslide presences, not confirmed non-landslide
observations or consistent event dates. Background points created here are
therefore *pseudo-absences*. The resulting model estimates inventory-based
spatial susceptibility, not a calibrated same-day landslide probability.
"""

import argparse
import csv
import json
import math
import random
from pathlib import Path

from sklearn.neighbors import BallTree

from app.scoring import FEATURE_ORDER

INDIA_BOUNDS = (6.0, 37.5, 68.0, 98.0)  # south, north, west, east
MINIMUM_BACKGROUND_DISTANCE_KM = 10.0


def _distance_ready(points: list[tuple[float, float]]) -> BallTree:
    radians = [[math.radians(lat), math.radians(lon)] for lat, lon in points]
    return BallTree(radians, metric="haversine")


def _base_row(latitude: float, longitude: float, label: int) -> dict[str, float | int]:
    # Event dates are incomplete in the source. Temporal weather columns are
    # deliberately neutral so the fitted model learns spatial susceptibility,
    # not fabricated historical weather associations.
    return {
        "latitude": round(latitude, 6), "longitude": round(longitude, 6),
        "rainfall_1h_mm": 0.0, "rainfall_6h_mm": 0.0,
        "rainfall_24h_mm": 0.0, "rainfall_7d_mm": 0.0,
        "temperature_c": 20.0, "humidity_percent": 70.0,
        "elevation_m": 0.0, "slope_degree": 0.0, "aspect_degree": 0.0,
        "historical_landslide_count": 0, "landslide_occurred": label,
    }


def build_dataset(source_path: str | Path, output_path: str | Path) -> dict[str, int]:
    source = Path(source_path)
    output = Path(output_path)
    document = json.loads(source.read_text(encoding="utf-8"))
    features = document.get("features", [])
    positives: list[tuple[float, float]] = []
    seen: set[tuple[float, float]] = set()
    for feature in features:
        geometry = feature.get("geometry") or {}
        if geometry.get("type") != "Point":
            continue
        coordinates = geometry.get("coordinates") or []
        if len(coordinates) < 2:
            continue
        longitude, latitude = float(coordinates[0]), float(coordinates[1])
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            continue
        key = (round(latitude, 6), round(longitude, 6))
        if key not in seen:
            seen.add(key)
            positives.append(key)
    if len(positives) < 100:
        raise ValueError("GSI inventory did not contain enough usable point records.")

    tree = _distance_ready(positives)
    rng = random.Random(20260906)
    negatives: list[tuple[float, float]] = []
    south, north, west, east = INDIA_BOUNDS
    minimum_radians = MINIMUM_BACKGROUND_DISTANCE_KM / 6371.0088
    while len(negatives) < len(positives):
        latitude, longitude = rng.uniform(south, north), rng.uniform(west, east)
        distance, _ = tree.query([[math.radians(latitude), math.radians(longitude)]], k=1)
        if float(distance[0][0]) >= minimum_radians:
            negatives.append((latitude, longitude))

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as destination:
        writer = csv.DictWriter(destination, fieldnames=FEATURE_ORDER + ["landslide_occurred"])
        writer.writeheader()
        writer.writerows(_base_row(lat, lon, 1) for lat, lon in positives)
        writer.writerows(_base_row(lat, lon, 0) for lat, lon in negatives)
    return {"positive_rows": len(positives), "pseudo_absence_rows": len(negatives)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build GSI India susceptibility data.")
    parser.add_argument("--source", default="data/raw/landslides/GSI_Landslide_Inventory.geojson")
    parser.add_argument("--output", default="data/gsi_india_susceptibility.csv")
    arguments = parser.parse_args()
    print(build_dataset(arguments.source, arguments.output))


if __name__ == "__main__":
    main()
