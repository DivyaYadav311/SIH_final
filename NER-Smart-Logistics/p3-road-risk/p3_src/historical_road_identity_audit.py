"""Audit retained source-derived road identity without geographic inference."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd

from .satellite_cv.road_geometry import road_identity
from .satellite_pipeline import EVENTS_PATH, eligible_events

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "data" / "reports"
SOURCE_PATH = ROOT / "data" / "raw" / "landslides" / "historical_landslides.geojson"
MANIFEST_PATH = ROOT / "data" / "raw" / "road_closure_evidence" / "source_manifests" / "sources.json"


def extract_identity(event: dict[str, Any], source_available: bool) -> dict[str, Any]:
    """Extract only identifiers written in retained source-derived fields."""
    original = str(event.get("road_name") or "").strip() or None
    evidence = str(event.get("evidence_text") or "").strip() or None
    classified = road_identity(event)
    source = "historical_landslides.geojson" if source_available else "processed road_closure_events.parquet (retained source-derived field; original GeoJSON absent)"
    base = {"road_name_original": original, "road_name_extracted": None, "highway_number_extracted": None,
            "route_name_extracted": None, "identity_source": source}
    if classified["road_name_quality"] == "NARRATIVE_TEXT":
        return {**base, "road_identity_quality": "NARRATIVE_ONLY", "identity_evidence": [f"road_name field: {original}", f"evidence_text: {evidence}"], "identity_confidence": "none"}
    # This inventory text identifies a direction/connection but does not label a
    # particular road segment or provide an NH/SH ref.
    route = re.search(r"\b(?:on\s+)?([A-Za-z ]+?\s+to\s+[A-Za-z ]+?\s+road)\b", original or "", re.I)
    if route:
        return {**base, "road_name_extracted": original, "route_name_extracted": route.group(1).strip(), "road_identity_quality": "EXPLICIT",
                "identity_evidence": [f"road_name field: {original}"], "identity_confidence": "medium" if not source_available else "high"}
    if classified["road_name_quality"] == "VALID":
        return {**base, "road_name_extracted": original, "road_identity_quality": "EXPLICIT",
                "identity_evidence": [f"road_name field: {original}"], "identity_confidence": "medium" if not source_available else "high"}
    if evidence and re.search(r"\broad\b", evidence, re.I):
        return {**base, "road_identity_quality": "PARTIAL", "identity_evidence": [f"road_name field: {original}", f"evidence_text: {evidence}"], "identity_confidence": "low"}
    return {**base, "road_identity_quality": "MISSING", "identity_evidence": ["No retained road identity text."], "identity_confidence": "none"}


def source_feature_for(event: dict[str, Any], features: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Find the original feature by its exact retained coordinate, not proximity."""
    for feature in features:
        prop, coords = feature.get("properties") or {}, (feature.get("geometry") or {}).get("coordinates") or []
        try:
            latitude = float(prop.get("LATITUDE", coords[1])); longitude = float(prop.get("LONGITUDE", coords[0]))
        except (TypeError, ValueError, IndexError):
            continue
        if latitude == float(event["latitude"]) and longitude == float(event["longitude"]): return prop
    return None


def run() -> dict[str, Any]:
    source_available = SOURCE_PATH.exists()
    events = [row.to_dict() for _, row in eligible_events(pd.read_parquet(EVENTS_PATH)).head(10).iterrows()]
    provenance = json.loads(MANIFEST_PATH.read_text()) if MANIFEST_PATH.exists() else {}
    features = json.loads(SOURCE_PATH.read_text()).get("features", []) if source_available else []
    rows = []
    for event in events:
        row = {"event_id": event["event_id"], "source_publisher": event.get("source_publisher"), "source_document": event.get("source_document"),
               "evidence_text": event.get("evidence_text"), "event_timestamp": event.get("event_timestamp"), "timestamp_source": event.get("timestamp_source"),
               "state": event.get("state"), "district": event.get("district"), "latitude": event.get("latitude"), "longitude": event.get("longitude"), "hazard_type": event.get("hazard_type")}
        extracted = extract_identity(event, source_available)
        feature = source_feature_for(event, features)
        if feature:
            extracted["identity_source"] = f"historical_landslides.geojson feature OBJECTID={feature.get('OBJECTID')} field NH_SH_LOCATION"
            extracted["identity_evidence"] = [f"NH_SH_LOCATION: {feature.get('NH_SH_LOCATION')}", f"COMMUNICATION_AFFECTED: {feature.get('COMMUNICATION_AFFECTED')}", f"INFRASTRUCTURE_AFFECTED: {feature.get('INFRASTRUCTURE_AFFECTED')}"]
            extracted["source_feature_id"] = feature.get("OBJECTID")
            extracted["road_name_original"] = str(feature.get("NH_SH_LOCATION") or "").strip() or None
        else:
            extracted["source_feature_id"] = None
        row.update(extracted); rows.append(row)
    qualities = ["EXPLICIT", "PARTIAL", "NARRATIVE_ONLY", "MISSING", "AMBIGUOUS"]
    aggregate = {"events_audited": len(rows), "original_source_available_locally": source_available,
                 "newly_identified_highway_references": 0, "newly_identified_road_names": 0,
                 **{quality.lower(): sum(row["road_identity_quality"] == quality for row in rows) for quality in qualities}}
    report = {"events": rows, "aggregate": aggregate, "provenance": {"source_manifest": str(MANIFEST_PATH.relative_to(ROOT)), "document_path": str(SOURCE_PATH.relative_to(ROOT)), "source_manifest_record": next((x for x in provenance.get("sources", []) if x.get("source_id") == "nrsc_historical_landslides_local"), None)}, "conclusion": "No newly supported road identity was recovered. The original GeoJSON is absent, so retained processed road_name values are reported as source-derived evidence with reduced confidence. No OSM rematch is justified."}
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "historical_road_identity_audit.json").write_text(json.dumps(report, indent=2, default=str))
    columns = ["event_id", "road_name_original", "road_name_extracted", "highway_number_extracted", "route_name_extracted", "road_identity_quality", "identity_confidence", "identity_evidence", "identity_source"]
    lines = ["# Historical road identity provenance audit", "", "## Aggregate", "", "```json", json.dumps(aggregate, indent=2), "```", "", "## Events", "", "| " + " | ".join(columns) + " |", "|" + "|".join(["---"] * len(columns)) + "|"]
    for row in rows: lines.append("| " + " | ".join(str(row.get(x, "")).replace("|", "/") for x in columns) + " |")
    lines.extend(["", "## Conclusion", "", report["conclusion"], ""])
    (REPORTS / "historical_road_identity_audit.md").write_text("\n".join(lines))
    return report


if __name__ == "__main__": print(json.dumps(run(), indent=2, default=str))
