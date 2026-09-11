"""Event-centred satellite sampling and feasibility audit for P3."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from .satellite_client import CDSEClient, buffer_bbox, event_windows

ROOT = Path(__file__).resolve().parents[1]
EVENTS_PATH = ROOT / "data" / "processed" / "road_closure" / "road_closure_events.parquet"
REPORTS = ROOT / "data" / "reports"
FEATURES_PATH = ROOT / "data" / "processed" / "features" / "p3_satellite_event_features.parquet"
CACHE = ROOT / "data" / "raw" / "satellite" / "cache"


def eligible_events(events: pd.DataFrame) -> pd.DataFrame:
    required = events[events.event_timestamp.notna() & events.latitude.notna() & events.longitude.notna()].copy()
    required["event_timestamp"] = pd.to_datetime(required["event_timestamp"], errors="coerce", utc=True)
    return required[required.event_timestamp.notna()].sort_values("event_id").reset_index(drop=True)


def candidate_record(event: pd.Series, satellite: str, product: dict[str, Any], phase: str) -> dict[str, Any]:
    acquisition = product.get("ContentDate", {}).get("Start") or product.get("acquisition_datetime")
    event_time = event.event_timestamp
    acquired = pd.to_datetime(acquisition, utc=True, errors="coerce")
    distance = None if pd.isna(acquired) else int((acquired.normalize() - event_time.normalize()).days)
    return {
        "event_id": event.event_id, "satellite": satellite, "product_id": product.get("Id") or product.get("product_id"),
        "acquisition_datetime": acquisition, "processing_level": product.get("processing_level") or product.get("Collection", {}).get("Name"),
        "cloud_cover": product.get("cloud_cover"), "orbit": product.get("orbit"), "distance_days": distance,
        "phase": phase, "spatial_overlap": product.get("spatial_overlap", True),
        "source_url": product.get("url") or product.get("@odata.id") or product.get("Id"),
    }


def build_feasibility(events: pd.DataFrame, observations: pd.DataFrame) -> dict[str, Any]:
    eligible = eligible_events(events)
    usable = observations[observations.product_id.notna()] if not observations.empty and "product_id" in observations else observations
    by_satellite = {sat: set(usable.loc[usable.satellite == sat, "event_id"]) for sat in ("sentinel-1", "sentinel-2")} if not usable.empty else {"sentinel-1": set(), "sentinel-2": set()}
    distances = pd.to_numeric(usable.distance_days, errors="coerce").abs() if not usable.empty else pd.Series(dtype=float)
    valid_distances = distances.dropna()
    def within(days: int) -> float | None:
        return None if eligible.empty else round(float((valid_distances <= days).sum() / len(eligible) * 100), 4)
    cloud = pd.to_numeric(usable.loc[usable.satellite == "sentinel-2", "cloud_cover"], errors="coerce") if not usable.empty else pd.Series(dtype=float)
    return {
        "events_examined": int(len(events)), "eligible_events": int(len(eligible)),
        "events_with_sentinel_1": len(by_satellite["sentinel-1"]), "events_with_sentinel_2": len(by_satellite["sentinel-2"]),
        "events_with_both": len(by_satellite["sentinel-1"] & by_satellite["sentinel-2"]),
        "median_temporal_gap_days": float(valid_distances.median()) if not valid_distances.empty else None,
        "usable_within_percent": {str(day): within(day) for day in (1, 3, 7, 14)},
        "sentinel_2_cloud_affected_percent": None if cloud.empty else round(float((cloud > 20).mean() * 100), 4),
        "observation_records": int(len(usable)), "missing_feature_rate_percent": 100.0 if usable.empty else None,
        "usable_training_samples": 0, "model_status": "insufficient_supervised_labels",
        "model_trained": False, "satellite_improved_prediction": False, "metrics": {},
        "notes": ["Only explicit event dates and valid coordinates are eligible.", "No unknown status was converted to an open label.", "No post-event observation is included in predictive_features."],
    }


def run(download: bool = False, buffer_m: float = 250.0, event_days: int = 1) -> dict[str, Any]:
    REPORTS.mkdir(parents=True, exist_ok=True)
    FEATURES_PATH.parent.mkdir(parents=True, exist_ok=True)
    events = pd.read_parquet(EVENTS_PATH) if EVENTS_PATH.exists() else pd.DataFrame()
    eligible = eligible_events(events) if not events.empty else pd.DataFrame()
    observations: list[dict[str, Any]] = []
    client = CDSEClient(CACHE) if download else None
    if download and not client.credentials_available():
        raise RuntimeError("Satellite acquisition requested but CDSE credentials are not configured")
    for _, event in eligible.iterrows():
        bbox = buffer_bbox(float(event.latitude), float(event.longitude), buffer_m)
        for satellite, collection, cloud in (("sentinel-1", "SENTINEL-1", None), ("sentinel-2", "SENTINEL-2", 20.0)):
            for phase, (start, end) in event_windows(event.event_timestamp.date().isoformat(), event_days).items():
                if client is None:
                    continue
                products = client.search_catalog(collection, bbox, start, end, cloud)
                observations.extend(candidate_record(event, satellite, product, phase) for product in products)
    observation_df = pd.DataFrame(observations, columns=["event_id", "satellite", "product_id", "acquisition_datetime", "processing_level", "cloud_cover", "orbit", "distance_days", "phase", "spatial_overlap", "source_url"])
    observation_df = observation_df.drop_duplicates(["event_id", "satellite", "product_id"]) if not observation_df.empty else observation_df
    rows = eligible.drop(columns=["road_closed"], errors="ignore").copy()
    rows["satellite_observation_count"] = rows.event_id.map(observation_df.event_id.value_counts()).fillna(0).astype(int) if not observation_df.empty else 0
    rows.to_parquet(FEATURES_PATH, index=False)
    report = build_feasibility(events, observation_df)
    report["buffer_m"] = buffer_m
    report["event_window_offsets_days"] = {
        "before_30_15": [-30, -15], "before_14_7": [-14, -7], "before_6_1": [-6, -1],
        "event": [-event_days, event_days], "after_1_6": [1, 6], "after_7_14": [7, 14], "after_15_30": [15, 30],
    }
    report["download_enabled"] = download
    (REPORTS / "satellite_feasibility.json").write_text(json.dumps(report, indent=2, default=str))
    (REPORTS / "satellite_observations.json").write_text(json.dumps(observations, indent=2, default=str))
    lines = ["# Satellite feasibility", "", f"- Historical events examined: {report['events_examined']}", f"- Eligible dated, coordinated events: {report['eligible_events']}", f"- Sentinel-1 events: {report['events_with_sentinel_1']}", f"- Sentinel-2 events: {report['events_with_sentinel_2']}", f"- Events with both: {report['events_with_both']}", f"- Median temporal gap (days): {report['median_temporal_gap_days']}", f"- Usable within 1/3/7/14 days (%): {report['usable_within_percent']}", f"- Sentinel-2 cloud affected (%): {report['sentinel_2_cloud_affected_percent']}", f"- Observation records: {report['observation_records']}", f"- Usable training samples: {report['usable_training_samples']}", "", "## Model status", "`insufficient_supervised_labels`: no binary model was trained because explicit open/reopened labels are absent.", "Post-event observations are retained only as verification metadata and are excluded from prediction-time features.", ""]
    (REPORTS / "satellite_feasibility.md").write_text("\n".join(lines))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit and optionally sample CDSE imagery around dated P3 events")
    parser.add_argument("--download", action="store_true", help="query CDSE; requires CDSE credentials")
    parser.add_argument("--buffer-m", type=float, default=250.0)
    parser.add_argument("--event-days", type=int, default=1)
    args = parser.parse_args()
    print(json.dumps(run(args.download, args.buffer_m, args.event_days), indent=2))


if __name__ == "__main__":
    main()