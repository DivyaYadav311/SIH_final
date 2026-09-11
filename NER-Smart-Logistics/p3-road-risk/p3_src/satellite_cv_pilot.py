"""Run a 10-event, human-auditable historical physical-road-status pilot."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .satellite_client import CDSEClient, buffer_bbox, credential_status, event_windows, process_payload
from .satellite_cv.change_detection import corridor_change
from .satellite_cv.labeling import assess_physical_road_status
from .satellite_cv.road_geometry import find_osm_road
from .satellite_cv.road_mask import road_mask_from_geometry
from .satellite_cv.visualization import save_comparison
from .satellite_pilot import arrays_from_tiff, product_record
from .satellite_pipeline import EVENTS_PATH, eligible_events

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "data" / "reports"
ARTIFACTS = REPORTS / "satellite_cv" / "events"
CACHE = ROOT / "data" / "raw" / "satellite" / "cache"
MANIFEST = ROOT / "data" / "raw" / "satellite" / "source_product_manifest.jsonl"


def _date_gap(product: dict[str, Any]) -> int | None:
    value = product.get("days_from_event")
    return None if value is None else abs(int(value))


def _select(products: list[dict[str, Any]], before: bool) -> dict[str, Any] | None:
    candidates = [product for product in products if (product["days_from_event"] < 0 if before else product["days_from_event"] > 0)]
    return min(candidates, key=lambda product: abs(product["days_from_event"]), default=None)


def run(limit: int = 10) -> dict[str, Any]:
    if limit > 10:
        raise ValueError("The CV proof-of-concept is capped at 10 events")
    REPORTS.mkdir(parents=True, exist_ok=True)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.touch(exist_ok=True)
    events = eligible_events(pd.read_parquet(EVENTS_PATH)).head(limit)
    report: dict[str, Any] = {"events_attempted": len(events), "successfully_processed": 0, "sentinel_1_available": 0, "sentinel_2_available": 0, "both_available": 0, "before_imagery_available": 0, "after_imagery_available": 0, "usable_before_after_pairs": 0, "open_candidates": 0, "disrupted_candidates": 0, "uncertain_candidates": 0, "manual_review_count": 0, "imagery_failures": [], "cv_failures": [], "insufficient_resolution_cases": 0, "cloud_related_exclusions": 0, "median_temporal_gap": None, "minimum_temporal_gap": None, "maximum_temporal_gap": None, "events": [], "model_trained": False, "disruption_probability": None, "model_status": "insufficient_supervised_labels", "road_geometry_status": "event_coordinate_buffer_fallback_no_verified_osm_geometry"}
    client = CDSEClient(CACHE)
    if not client.credentials_available():
        report["imagery_failures"].append("CDSE credentials are not configured")
        report["events"] = [{"event_id": row.event_id, "event_date": row.event_timestamp.date().isoformat(), "physical_road_status": "UNCERTAIN", "confidence": 0.0, "reason": "authentication_blocked"} for _, row in events.iterrows()]
        _write(report, "blocked_pending_credentials")
        return report
    gaps: list[int] = []
    with MANIFEST.open("a") as manifest:
        for _, event in events.iterrows():
            result: dict[str, Any] = {"event_id": event.event_id, "event_date": event.event_timestamp.date().isoformat(), "latitude": float(event.latitude), "longitude": float(event.longitude), "road_name": event.get("road_name"), "satellite": None, "before_date": None, "after_date": None, "days_before": None, "days_after": None, "physical_road_status": "UNCERTAIN", "confidence": 0.0, "reason": "not_processed", "artifact_path": None}
            geometry = find_osm_road(result, CACHE / "osm")
            result.update({"geometry_source": geometry.get("geometry_source"), "osm_way_id": geometry.get("osm_way_id"), "geometry_match_status": geometry.get("match_status")})
            selected: dict[str, dict[str, Any] | None] = {"sentinel-1": None, "sentinel-2": None}
            arrays: dict[str, dict[str, np.ndarray]] = {}
            try:
                for satellite, collection, cloud in (("sentinel-1", "SENTINEL-1", None), ("sentinel-2", "SENTINEL-2", 20.0)):
                    products: list[dict[str, Any]] = []
                    for phase in ("before_30_15", "before_14_7", "before_6_1", "event", "after_1_6", "after_7_14"):
                        start, end = event_windows(result["event_date"])[phase]
                        for product in client.search_catalog(collection, buffer_bbox(result["latitude"], result["longitude"]), start, end, cloud):
                            record = product_record(event, satellite, product, phase)
                            products.append(record)
                            manifest.write(json.dumps(record) + "\n")
                    before = _select(products, True)
                    after = _select(products, False)
                    selected[satellite] = {"before": before, "after": after}
                    if before and after:
                        for key, product in (("before", before), ("after", after)):
                            start, end = event_windows(result["event_date"])[product["phase"]]
                            payload = process_payload(satellite, buffer_bbox(result["latitude"], result["longitude"]), start, end, product["product_id"])
                            content, cached, digest = client.process_cached(payload)
                            arrays.setdefault(satellite, {})[key] = np.asarray(next(iter(arrays_from_tiff(content, satellite).values())), dtype=float).reshape(32, 32)
                            product["request_sha256"] = digest
                            product["download_cached"] = cached
                            product["download_sha256"] = hashlib.sha256(content).hexdigest()
                available = {satellite: pair for satellite, pair in selected.items() if pair["before"] and pair["after"]}
                report["sentinel_1_available"] += int("sentinel-1" in available)
                report["sentinel_2_available"] += int("sentinel-2" in available)
                report["both_available"] += int(len(available) == 2)
                pair = available.get("sentinel-1") or available.get("sentinel-2")
                if pair:
                    report["before_imagery_available"] += 1
                    report["after_imagery_available"] += 1
                    before, after = pair["before"], pair["after"]
                    result.update({"satellite": "sentinel-1" if "sentinel-1" in available else "sentinel-2", "before_date": before["acquisition_datetime"], "after_date": after["acquisition_datetime"], "days_before": abs(before["days_from_event"]), "days_after": after["days_from_event"]})
                    gaps.extend([result["days_before"], result["days_after"]])
                    geometry_input = None
                    if geometry.get("geometry"):
                        geometry_input = {"coordinates": geometry["geometry"], "bbox": buffer_bbox(result["latitude"], result["longitude"])}
                    mask, mask_reason = road_mask_from_geometry(32, 32, geometry_input)
                    comparison = corridor_change(arrays[result["satellite"]]["before"], arrays[result["satellite"]]["after"], mask)
                    decision = assess_physical_road_status(comparison["changed_fraction"], True, True, result["days_before"], result["days_after"], background_mean=comparison.get("background_mean"), corridor_mean=comparison.get("corridor_mean"), geometry_source=result["geometry_source"])
                    result.update({"physical_road_status": decision["physical_road_status"], "confidence": decision["disruption_confidence"], "manual_review_required": decision["manual_review_required"], "reason": decision["reason"], "road_mask": mask_reason, "road_change_fraction": comparison["changed_fraction"], "change_score": comparison["corridor_mean"], "background_change_score": comparison.get("background_mean"), "road_change_concentration": comparison.get("road_change_concentration")})
                    result["artifact_path"] = str(Path("data/reports/satellite_cv/events") / str(event.event_id))
                    save_comparison(arrays[result["satellite"]]["before"], arrays[result["satellite"]]["after"], comparison["change_map"], mask, ARTIFACTS / str(event.event_id))
                    report["usable_before_after_pairs"] += 1
                    report["successfully_processed"] += 1
                else:
                    result["reason"] = "no_usable_before_after_pair"
            except Exception as error:
                report["cv_failures"].append({"event_id": event.event_id, "error": str(error)})
                result["reason"] = "processing_failure"
            report["events"].append(result)
    report["open_candidates"] = sum(event["physical_road_status"] == "OPEN" for event in report["events"])
    report["disrupted_candidates"] = sum(event["physical_road_status"] == "DISRUPTED" for event in report["events"])
    report["uncertain_candidates"] = sum(event["physical_road_status"] == "UNCERTAIN" for event in report["events"])
    report["manual_review_count"] = sum(bool(event.get("manual_review_required", True)) for event in report["events"])
    if gaps:
        report["median_temporal_gap"] = float(np.median(gaps))
        report["minimum_temporal_gap"], report["maximum_temporal_gap"] = min(gaps), max(gaps)
    _write(report, "B. Potentially feasible but needs manual validation" if report["usable_before_after_pairs"] else "C. Not currently feasible")
    _write_manual_validation(report)
    _write_validation_report(report)
    return report


def _write(report: dict[str, Any], conclusion: str) -> None:
    report["conclusion"] = conclusion
    (REPORTS / "satellite_cv_pilot_results.json").write_text(json.dumps(report, indent=2, default=str))
    summary = {key: value for key, value in report.items() if key != "events"}
    rows = [
        "| event_id | event_date | latitude | longitude | road_name | satellite | before_date | after_date | days_before | days_after | status | confidence | reason | artifact_path |",
        "|---|---|---:|---:|---|---|---|---|---:|---:|---|---:|---|---|",
    ]
    for event in report["events"]:
        rows.append("| " + " | ".join(str(event.get(key, "")).replace("|", "/") for key in (
            "event_id", "event_date", "latitude", "longitude", "road_name", "satellite", "before_date",
            "after_date", "days_before", "days_after", "physical_road_status", "confidence", "reason", "artifact_path",
        )) + " |")
    markdown = "# Satellite CV pilot results\n\n## Summary\n\n```json\n" + json.dumps(summary, indent=2, default=str) + "\n```\n\n## Event results\n\n" + "\n".join(rows) + "\n"
    (REPORTS / "satellite_cv_pilot_results.md").write_text(markdown)


def _write_manual_validation(report: dict[str, Any]) -> None:
    frame = pd.DataFrame([{"event_id": event["event_id"], "cv_label": event.get("physical_road_status", "UNCERTAIN"), "cv_confidence": event.get("confidence", 0.0), "human_label": "NOT_REVIEWED", "human_confidence": "", "agreement": "", "notes": "Inspect event artifact before entering a human label."} for event in report["events"]])
    frame.to_csv(REPORTS / "satellite_cv" / "manual_validation.csv", index=False)


def _write_validation_report(report: dict[str, Any]) -> None:
    validation = {"events_attempted": report["events_attempted"], "successfully_processed": report["successfully_processed"], "osm_matching_success": sum(event.get("geometry_source") == "osm_overpass" for event in report["events"]), "geometry_sources": pd.Series([event.get("geometry_source", "unknown") for event in report["events"]]).value_counts().to_dict(), "sentinel_1_available": report["sentinel_1_available"], "sentinel_2_available": report["sentinel_2_available"], "candidate_labels": {"OPEN": report["open_candidates"], "DISRUPTED": report["disrupted_candidates"], "UNCERTAIN": report["uncertain_candidates"]}, "manual_review_required": report["manual_review_count"], "visual_artifacts": [event.get("artifact_path") for event in report["events"] if event.get("artifact_path")], "manual_metrics": "not calculated; all human_label values are NOT_REVIEWED", "scale_decision": "B = CV needs further improvement", "recommended_next_step": "Manually inspect all generated artifacts, improve verified road geometry, then reassess before any expansion.", "limitations": ["No verified local OSM index; Overpass matching may fall back to coordinate buffers.", "Sentinel-2 had no usable pairs in the pilot.", "SAR change is an environmental change signal, not proof of physical road disruption.", "No post-event imagery is used as a predictive feature."]}
    (REPORTS / "satellite_cv_validation_results.json").write_text(json.dumps(validation, indent=2, default=str))
    (REPORTS / "satellite_cv_validation_results.md").write_text("# Satellite CV validation\n\n```json\n" + json.dumps(validation, indent=2, default=str) + "\n```\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the first 10-event satellite CV labeling pilot")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--check-config", action="store_true")
    args = parser.parse_args()
    if args.check_config:
        print(json.dumps(credential_status()))
        return
    print(json.dumps(run(args.limit), indent=2, default=str))


if __name__ == "__main__":
    main()