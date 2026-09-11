"""Normalize the supplied INDOFLOODS files into an auditable event table.

This creates positive flood-event examples and catchment centroids. It does not
invent negative labels: a separate historical rainfall/source-coverage step is
required before the result can be used for supervised training.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd
import shapefile


GAUGE_RE = re.compile(r"INDOFLOODS-gauge-(\d+)-")


def _gauge_id(event_id: str) -> str:
    match = GAUGE_RE.match(str(event_id))
    if not match:
        raise ValueError(f"Unexpected INDOFLOODS EventID: {event_id}")
    return f"INDOFLOODS-gauge-{match.group(1)}"


def load_centroids(shapefile_root: Path) -> pd.DataFrame:
    rows = []
    for path in sorted(shapefile_root.rglob("*.shp")):
        gauge_id = path.stem
        reader = shapefile.Reader(str(path))
        if not reader.shapes():
            continue
        bbox = reader.shape(0).bbox
        rows.append({
            "gauge_id": gauge_id,
            "latitude": round((bbox[1] + bbox[3]) / 2, 6),
            "longitude": round((bbox[0] + bbox[2]) / 2, 6),
            "geometry_source": str(path),
        })
    result = pd.DataFrame(rows)
    if result.empty:
        raise ValueError(f"No catchment shapefiles found under {shapefile_root}")
    return result


def build_event_table(events_path: Path, precipitation_path: Path, characteristics_path: Path, shapefile_root: Path) -> pd.DataFrame:
    events = pd.read_csv(events_path)
    precipitation = pd.read_csv(precipitation_path)
    characteristics = pd.read_csv(characteristics_path)
    centroids = load_centroids(shapefile_root)

    events["gauge_id"] = events["EventID"].map(_gauge_id)
    events["date"] = pd.to_datetime(events["Start Date"], errors="coerce")
    events["end_date"] = pd.to_datetime(events["End Date"], errors="coerce")
    if events["date"].isna().any():
        raise ValueError("INDOFLOODS contains invalid event dates")

    rainfall = precipitation.rename(columns={
        "T1d": "rainfall_1d_mm", "T3d": "rainfall_3d_mm",
        "T7d": "rainfall_7d_mm", "T10d": "rainfall_10d_mm",
    })
    keep_rain = ["EventID", "rainfall_1d_mm", "rainfall_3d_mm", "rainfall_7d_mm", "rainfall_10d_mm"]
    rainfall = rainfall[[column for column in keep_rain if column in rainfall.columns]]
    output = events.merge(rainfall, on="EventID", how="left", validate="one_to_one")
    output = output.merge(centroids, on="gauge_id", how="left", validate="many_to_one")

    characteristics = characteristics.rename(columns={"GaugeID": "gauge_id"})
    static_columns = [
        "gauge_id", "Drainage Area", "Catchment Relief", "Drainage Density",
        "Annual Precipitation", "Road Density", "Urban percentage",
        "Population Density", "Land cover", "Soil type", "lithology type",
    ]
    static = characteristics[[column for column in static_columns if column in characteristics.columns]]
    output = output.merge(static, on="gauge_id", how="left", validate="many_to_one")
    output["segment_id"] = output["gauge_id"]
    output["flood_event"] = 1
    output["label_source"] = "INDOFLOODS_observed_event"
    output["forecast_horizon_days"] = 3
    output["month"] = output["date"].dt.month
    return output.sort_values(["date", "gauge_id", "EventID"]).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", type=Path, default=Path(__file__).resolve().parent.parent / "data/raw/hydrosense")
    parser.add_argument("--shapefile-root", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent.parent / "data/processed/indofloods_event_candidates.csv")
    args = parser.parse_args()
    shape_root = args.shapefile_root or args.raw_dir / "catchments/catchments_shapefiles_indofloods"
    table = build_event_table(
        args.raw_dir / "floodevents_indofloods.csv",
        args.raw_dir / "precipitation_variables_indofloods.csv",
        args.raw_dir / "catchment_characteristics_indofloods.csv",
        shape_root,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(args.output, index=False)
    print(f"Wrote {len(table)} observed flood events across {table['gauge_id'].nunique()} catchments")
    print("This file contains positive events only; it is not yet a supervised training table.")


if __name__ == "__main__":
    main()
