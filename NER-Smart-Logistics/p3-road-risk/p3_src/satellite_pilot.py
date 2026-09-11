"""Run the capped, real CDSE acquisition pilot for the first 20 eligible events."""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
from typing import Any

import pandas as pd
import numpy as np
import tifffile

from .satellite_client import CDSEClient, buffer_bbox, credential_status, event_windows, process_payload
from .satellite_features import extract_s1_features, extract_s2_features, predictive_features
from .satellite_pipeline import EVENTS_PATH, eligible_events

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "data" / "reports"
CACHE = ROOT / "data" / "raw" / "satellite" / "cache"
MANIFEST = ROOT / "data" / "raw" / "satellite" / "source_product_manifest.jsonl"


def product_cloud(product: dict[str, Any]) -> float | None:
    for attribute in product.get("Attributes", {}).get("OData.CSC.DoubleAttribute", []):
        if attribute.get("Name", "").lower() in {"cloudcover", "cloudcoverpercentage"}:
            return attribute.get("Value")
    return product.get("cloud_cover")


def product_record(event: pd.Series, satellite: str, product: dict[str, Any], phase: str) -> dict[str, Any]:
    acquisition = product.get("ContentDate", {}).get("Start")
    acquired = pd.to_datetime(acquisition, utc=True, errors="coerce")
    event_date = pd.to_datetime(event.event_timestamp, utc=True)
    gap = None if pd.isna(acquired) else int((acquired.normalize() - event_date.normalize()).days)
    return {
        "event_id": event.event_id, "event_date": event.event_timestamp.date().isoformat(),
        "latitude": float(event.latitude), "longitude": float(event.longitude), "satellite": satellite,
        "phase": phase, "product_id": product.get("Id"), "product_name": product.get("Name"),
        "acquisition_datetime": acquisition, "days_from_event": gap, "cloud_cover": product_cloud(product),
        "processing_level": product.get("Collection", {}).get("Name"), "source_url": product.get("@odata.id"),
    }


def retrieve_nearest(client: CDSEClient, event: pd.Series, satellite: str, nearest: dict[str, Any], buffer_m: float) -> dict[str, Any]:
    start, end = event_windows(nearest["event_date"])[nearest["phase"]]
    payload = process_payload(
        satellite, buffer_bbox(float(event.latitude), float(event.longitude), buffer_m), start, end,
        nearest["product_id"],
    )
    content, cached, digest = client.process_cached(payload)
    result = {"cache_key": digest, "cached": cached, "bytes": len(content), "sha256": __import__("hashlib").sha256(content).hexdigest()}
    try:
        arrays = arrays_from_tiff(content, satellite)
        result["bands"] = list(arrays)
        result["features"] = predictive_features(
            extract_s1_features({nearest["phase"]: arrays})
            if satellite == "sentinel-1" else extract_s2_features({nearest["phase"]: arrays})
        )
        result["extraction_status"] = "success"
    except Exception as error:
        result["extraction_status"] = "failed"
        result["extraction_error"] = str(error)
    return result


def arrays_from_tiff(content: bytes, satellite: str) -> dict[str, list[float]]:
    pages = tifffile.imread(io.BytesIO(content))
    names = ["vv", "vh"] if satellite == "sentinel-1" else ["b02", "b03", "b04", "b08", "b11", "b12", "scl"]
    if getattr(pages, "ndim", 0) == 2:
        array = pages[None, ...]
    elif pages.shape[0] == len(names):
        array = pages
    elif pages.shape[-1] == len(names):
        array = np.moveaxis(pages, -1, 0)
    else:
        raise ValueError(f"unexpected raster shape {pages.shape} for {satellite}")
    return {name: array[index].reshape(-1).tolist() for index, name in enumerate(names) if index < len(array)}


def run_pilot(limit: int = 20, buffer_m: float = 250.0) -> dict[str, Any]:
    REPORTS.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.touch(exist_ok=True)
    events = eligible_events(pd.read_parquet(EVENTS_PATH)).head(limit)
    client = CDSEClient(CACHE)
    report: dict[str, Any] = {
        "events_attempted": len(events), "events_successfully_queried": 0, "sentinel_1_availability": 0,
        "sentinel_2_availability": 0, "both_available": 0, "no_imagery": 0, "nearest_acquisition_gaps": {},
        "cloud_statistics": {}, "extraction_failures": [], "feature_completeness": {}, "api_failures": [],
        "rate_limit_failures": 0, "model_trained": False, "disruption_probability": None,
        "model_status": "insufficient_supervised_labels", "conclusion": None, "events": [],
        "acquisition_scope": "pilot_only_first_20_eligible_events", "post_event_used_for_prediction": False,
    }
    if not client.credentials_available():
        report["api_failures"].append({"stage": "authentication", "error": "CDSE credentials are not configured"})
        report["events"] = [
            {"event_id": event.event_id, "event_date": event.event_timestamp.date().isoformat(),
             "latitude": float(event.latitude), "longitude": float(event.longitude),
             "query_status": "authentication_blocked", "download_request_status": "not_attempted"}
            for _, event in events.iterrows()
        ]
        report["conclusion"] = "blocked_pending_credentials"
        (REPORTS / "satellite_pilot_results.json").write_text(json.dumps(report, indent=2))
        (REPORTS / "satellite_pilot_results.md").write_text("# Satellite pilot results\n\nAuthentication was blocked because CDSE_CLIENT_ID and CDSE_CLIENT_SECRET are not configured. No imagery availability conclusion was inferred from missing credentials.\n")
        return report
    with MANIFEST.open("a") as manifest:
        for _, event in events.iterrows():
            event_result: dict[str, Any] = {"event_id": event.event_id, "event_date": event.event_timestamp.date().isoformat(), "latitude": float(event.latitude), "longitude": float(event.longitude), "satellite": {"sentinel-1": {"products": [], "query_status": "not_attempted", "request_status": "not_attempted"}, "sentinel-2": {"products": [], "query_status": "not_attempted", "request_status": "not_attempted"}}}
            for satellite, collection, cloud in (("sentinel-1", "SENTINEL-1", None), ("sentinel-2", "SENTINEL-2", 20.0)):
                for phase in ("before_30_15", "before_14_7", "before_6_1", "event"):
                    start, end = event_windows(event_result["event_date"])[phase]
                    try:
                        products = client.search_catalog(collection, buffer_bbox(float(event.latitude), float(event.longitude), buffer_m), start, end, cloud)
                        event_result["satellite"][satellite]["query_status"] = "success"
                    except Exception as error:
                        event_result["satellite"][satellite]["query_status"] = "failed"
                        report["api_failures"].append({"event_id": event.event_id, "satellite": satellite, "phase": phase, "error": str(error)})
                        products = []
                    for product in products:
                        record = product_record(event, satellite, product, phase)
                        event_result["satellite"][satellite]["products"].append(record)
                        manifest.write(json.dumps(record) + "\n")
            for satellite in ("sentinel-1", "sentinel-2"):
                products = event_result["satellite"][satellite]["products"]
                if products:
                    event_result["satellite"][satellite]["nearest"] = min(products, key=lambda item: abs(item["days_from_event"] or 10**9))
                    try:
                        event_result["satellite"][satellite]["request"] = retrieve_nearest(client, event, satellite, event_result["satellite"][satellite]["nearest"], buffer_m)
                        event_result["satellite"][satellite]["request_status"] = "tile_obtained"
                    except Exception as error:
                        event_result["satellite"][satellite]["request_status"] = "failed"
                        report["api_failures"].append({"event_id": event.event_id, "satellite": satellite, "stage": "process", "error": str(error)})
            report["events"].append(event_result)
    report["events_successfully_queried"] = sum(any(value["query_status"] == "success" for value in result["satellite"].values()) for result in report["events"])
    report["sentinel_1_availability"] = sum(bool(result["satellite"]["sentinel-1"]["products"]) for result in report["events"])
    report["sentinel_2_availability"] = sum(bool(result["satellite"]["sentinel-2"]["products"]) for result in report["events"])
    report["both_available"] = sum(bool(result["satellite"]["sentinel-1"]["products"]) and bool(result["satellite"]["sentinel-2"]["products"]) for result in report["events"])
    report["no_imagery"] = sum(not result["satellite"]["sentinel-1"]["products"] and not result["satellite"]["sentinel-2"]["products"] for result in report["events"])
    report["conclusion"] = "B. Potentially feasible but needs more data" if report["both_available"] else "C. Not currently feasible"
    (REPORTS / "satellite_pilot_results.json").write_text(json.dumps(report, indent=2, default=str))
    (REPORTS / "satellite_pilot_results.md").write_text("# Satellite pilot results\n\n" + json.dumps({key: value for key, value in report.items() if key != "events"}, indent=2, default=str) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the first-20-event CDSE satellite pilot")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--check-config", action="store_true", help="report CDSE credential presence without values")
    args = parser.parse_args()
    if args.check_config:
        print(json.dumps(credential_status()))
        return
    if args.limit > 20:
        raise ValueError("Pilot is capped at 20 events; scaling requires an explicit separate change")
    print(json.dumps(run_pilot(args.limit), indent=2, default=str))


if __name__ == "__main__":
    main()