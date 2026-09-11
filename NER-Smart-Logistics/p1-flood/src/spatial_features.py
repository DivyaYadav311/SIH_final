"""Small, dependency-light spatial features for P1.

The NWIC river download is a projected shapefile, but it also publishes a
latitude/longitude representative point for each river segment.  Those points
are sufficient for a consistent nearest-river feature and avoid requiring a
full GIS stack in the training environment.  The feature is an approximation,
not a replacement for a hydrologic distance calculation.
"""

from __future__ import annotations

import json
import math
import argparse
import tempfile
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import shapefile


def haversine_km(lat1: float, lon1: float, lat2: np.ndarray, lon2: np.ndarray) -> np.ndarray:
    radius_km = 6371.0
    p1 = np.radians(lat1)
    p2 = np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlambda / 2) ** 2
    return 2 * radius_km * np.arcsin(np.sqrt(a))


def load_river_points(river_zip: Path) -> pd.DataFrame:
    """Read representative river points from the NWIC shapefile archive."""
    with zipfile.ZipFile(river_zip) as archive, tempfile.TemporaryDirectory(prefix="p1_rivers_") as temp:
        archive.extractall(temp)
        reader = shapefile.Reader(str(Path(temp) / "River_Network.shp"))
        fields = [field[0] for field in reader.fields[1:]]
        rows = []
        for values in reader.iterRecords():
            row = dict(zip(fields, values))
            try:
                lat = float(row["lat"])
                lon = float(row["long"])
            except (KeyError, TypeError, ValueError):
                continue
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                rows.append({
                    "river_name": row.get("rivname"),
                    "river_latitude": lat,
                    "river_longitude": lon,
                    "river_length_km": row.get("length_km"),
                    "river_uid": row.get("UID_River"),
                })
        result = pd.DataFrame(rows).drop_duplicates(subset=["river_latitude", "river_longitude"])
    if result.empty:
        raise ValueError(f"No valid latitude/longitude river points found in {river_zip}")
    return result.reset_index(drop=True)


def nearest_river_km(lat: float, lon: float, river_points: pd.DataFrame) -> float:
    distances = haversine_km(
        float(lat),
        float(lon),
        river_points["river_latitude"].to_numpy(dtype=float),
        river_points["river_longitude"].to_numpy(dtype=float),
    )
    return round(float(np.nanmin(distances)), 3)


def add_river_proximity(frame: pd.DataFrame, river_zip: Path) -> pd.DataFrame:
    """Add an auditable approximate nearest-river feature to latitude/longitude rows."""
    required = {"latitude", "longitude"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Cannot calculate river proximity; missing {sorted(missing)}")
    points = load_river_points(river_zip)
    output = frame.copy()
    # Daily training tables repeat each catchment many times. Calculate the
    # spatial join once per unique coordinate, then merge it back.
    coordinates = output[["latitude", "longitude"]].drop_duplicates().copy()
    coordinates["river_proximity_km"] = [
        nearest_river_km(lat, lon, points) if pd.notna(lat) and pd.notna(lon) else np.nan
        for lat, lon in zip(coordinates["latitude"], coordinates["longitude"])
    ]
    output = output.drop(columns=["river_proximity_km"], errors="ignore").merge(
        coordinates, on=["latitude", "longitude"], how="left", validate="many_to_one"
    )
    output["river_feature_source"] = "NWIC_River_Network_representative_points"
    return output


def write_spatial_audit(river_zip: Path, road_pbf: Path, output: Path) -> dict:
    river_points = load_river_points(river_zip)
    audit = {
        "river_source": str(river_zip),
        "river_feature_count": int(len(river_points)),
        "river_feature_method": "nearest NWIC representative latitude/longitude point",
        "road_source": str(road_pbf),
        "road_source_bytes": road_pbf.stat().st_size,
        "road_parser_status": "source_present_parser_not_required_for_P1_catchment_features",
        "elevation_status": "unavailable_without_CartoDEM; live Open-Meteo elevation remains fallback",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(audit, indent=2) + "\n")
    return audit


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description="Audit P1 river and road spatial sources")
    parser.add_argument("--river-zip", type=Path, default=root / "data/raw/rivers/river_network_shape.zip")
    parser.add_argument("--road-pbf", type=Path, default=root / "data/raw/roads/north-eastern-zone-260907.osm.pbf")
    parser.add_argument("--output", type=Path, default=root / "data/reports/p1_spatial_audit.json")
    args = parser.parse_args()
    audit = write_spatial_audit(args.river_zip, args.road_pbf, args.output)
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
