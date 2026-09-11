"""Write the bounded ten-event OSM geometry and candidate audits."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
from PIL import Image, ImageDraw

from .satellite_cv.road_geometry import DEFAULT_PBF, LAST_PBF_STATS, _score_candidate, _select, match_local_pbf_events, road_identity
from .satellite_pipeline import EVENTS_PATH, eligible_events

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "data" / "reports"
REVIEW_DIR = REPORTS / "osm_geometry_review"
EVENT_FIELDS = ["event_id", "road_name", "highway_number", "road_type", "state", "district", "city_or_town", "latitude", "longitude", "evidence_text", "source_publisher", "source_document", "hazard_type", "closure_status", "event_timestamp", "timestamp_source"]


def _safe(value: Any) -> str:
    return "" if value is None else str(value).replace("|", "/").replace("\n", " ")


def _overlay(event: dict[str, Any], source: dict[str, Any]) -> str:
    """Small deterministic geometry-review image for an accepted review candidate."""
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    candidates = source["all_candidates"]
    points = [(float(event["longitude"]), float(event["latitude"]))]
    for candidate in candidates:
        points.extend((float(x), float(y)) for x, y in candidate["geometry"])
    min_x, max_x = min(x for x, _ in points), max(x for x, _ in points); min_y, max_y = min(y for _, y in points), max(y for _, y in points)
    pad_x, pad_y = max((max_x - min_x) * .08, .002), max((max_y - min_y) * .08, .002)
    width, height = 1000, 760
    def xy(point: list[float] | tuple[float, float]) -> tuple[int, int]:
        return (int(50 + (point[0] - min_x + pad_x) / (max_x - min_x + 2 * pad_x) * 900), int(710 - (point[1] - min_y + pad_y) / (max_y - min_y + 2 * pad_y) * 620))
    image = Image.new("RGB", (width, height), "white"); draw = ImageDraw.Draw(image)
    selected = source.get("osm_way_id")
    for candidate in candidates:
        line = [xy(point) for point in candidate["geometry"]]
        color = "#d62728" if candidate["osm_way_id"] == selected else "#777777"
        draw.line(line, fill=color, width=4 if candidate["osm_way_id"] == selected else 2)
        if line:
            draw.text(line[len(line)//2], f"{candidate['osm_way_id']} {candidate.get('name') or ''} {candidate.get('ref') or ''} [{candidate.get('highway')}]", fill=color)
    ex, ey = xy((float(event["longitude"]), float(event["latitude"]))); draw.ellipse((ex - 7, ey - 7, ex + 7, ey + 7), fill="#0066cc")
    draw.text((20, 20), f"Event {event['event_id']} — {source['match_status']} (blue=event, red=selected)", fill="black")
    path = REVIEW_DIR / f"{event['event_id']}.png"; image.save(path)
    return str(path.relative_to(ROOT))


def _markdown(title: str, payload: dict[str, Any], rows: list[dict[str, Any]], columns: list[str]) -> str:
    lines = [f"# {title}", "", "## Aggregate", "", "```json", json.dumps(payload["aggregate"], indent=2), "```", "", "## Events", "", "| " + " | ".join(columns) + " |", "|" + "|".join(["---"] * len(columns)) + "|"]
    for row in rows: lines.append("| " + " | ".join(_safe(row.get(col)) for col in columns) + " |")
    lines.extend(["", "## Interpretation", "", payload["interpretation"], ""])
    return "\n".join(lines)


def _reassess_previous(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Re-score the preserved parser output when a full stream is unavailable.

    This is only a reproducibility path for the existing 10-event audit; it never
    fetches data, creates candidates, or substitutes a candidate for a fallback.
    """
    previous = json.loads((REPORTS / "osm_road_matching_results.json").read_text())
    prior_aggregate = previous.get("aggregate", {})
    # Preserve provenance from the completed local-PBF stream which produced the
    # retained candidates; this mode does not claim to have streamed it again.
    LAST_PBF_STATS.update({"parser_available": bool(prior_aggregate.get("local_pbf_parser_available", True)),
                           "ways_examined": int(prior_aggregate.get("pbf_ways_examined", 0)),
                           "candidate_ways": int(prior_aggregate.get("candidate_ways", prior_aggregate.get("total_candidates", 0)))})
    old_by_id = {str(row["event_id"]): row.get("candidate_summaries", []) for row in previous.get("events", [])}
    if not any(old_by_id.values()):
        preserved = json.loads((REPORTS / "osm_candidate_audit.json").read_text())
        old_by_id = {}
        for candidate in preserved.get("candidates", []): old_by_id.setdefault(str(candidate["event_id"]), []).append(candidate)
    output = {}
    for event in events:
        raw = old_by_id.get(str(event["event_id"]), [])
        candidates = []
        for item in raw:
            geometry = [{"lon": point[0], "lat": point[1]} for point in item.get("geometry", [])]
            candidates.append(_score_candidate(event, {"id": item["osm_way_id"], "tags": item.get("tags", {}), "geometry": geometry, "distance_from_event": item.get("distance_from_event", item.get("distance_m"))}))
        candidates.sort(key=lambda c: (c["distance_m"] if c["distance_m"] is not None else float("inf"), c["osm_way_id"]))
        decision = _select(event, candidates); selected = decision.pop("selected_candidate")
        output[str(event["event_id"])] = {**road_identity(event), **decision, "all_candidates": candidates, "geometry_source": "osm_local_pbf" if selected else "coordinate_buffer", "matching_confidence": decision["match_status"], "osm_way_id": selected["osm_way_id"] if selected else None, "osm_road_name": selected["name"] if selected else None, "osm_ref": selected["ref"] if selected else None, "osm_highway_type": selected["highway"] if selected else None, "distance_from_event": selected["distance_m"] if selected else None, "geometry": selected["geometry"] if selected else [], "matching_method": "preserved_local_pbf_candidate_reassessment"}
    return output


def run(use_previous_audit: bool = False) -> dict[str, Any]:
    events = eligible_events(pd.read_parquet(EVENTS_PATH)).head(10)
    records = [row.to_dict() for _, row in events.iterrows()]
    sources = _reassess_previous(records) if use_previous_audit else match_local_pbf_events(records)
    results, candidate_rows = [], []
    for event in records:
        source = sources[str(event["event_id"])]
        result = {field: event.get(field) for field in EVENT_FIELDS}
        result.update({key: source.get(key) for key in ("road_name_raw", "road_name_normalized", "road_name_quality", "extracted_highway_ref", "identity_evidence", "match_status", "match_reason", "nearest_candidate_distance", "second_nearest_candidate_distance", "distance_gap", "candidate_count", "number_of_distinct_road_classes", "distinct_road_classes", "osm_way_id", "osm_road_name", "osm_ref", "osm_highway_type", "distance_from_event", "geometry_source", "matching_method")})
        result["manual_review_required"] = source["match_status"] in {"HIGH_CONFIDENCE", "MEDIUM_CONFIDENCE"}
        result["geometry_review_overlay"] = _overlay(event, source) if result["manual_review_required"] else None
        results.append(result)
        for candidate in source["all_candidates"]:
            candidate_rows.append({"event_id": event["event_id"], **candidate})
    statuses = ["HIGH_CONFIDENCE", "MEDIUM_CONFIDENCE", "AMBIGUOUS", "NO_RELIABLE_MATCH", "COORDINATE_FALLBACK"]
    aggregate = {"events_audited": len(results), "valid_road_identifiers": sum(x["road_name_quality"] == "VALID" for x in results), "narrative_road_names": sum(x["road_name_quality"] == "NARRATIVE_TEXT" for x in results), "total_candidates": len(candidate_rows), "valid_geometries": sum(x["geometry_valid"] for x in candidate_rows), "rejected_candidates": sum(x["rejection_reason"] is not None for x in candidate_rows), "local_pbf_present": DEFAULT_PBF.exists(), "local_pbf_parser_available": bool(LAST_PBF_STATS["parser_available"]), "pbf_ways_examined": int(LAST_PBF_STATS["ways_examined"])}
    aggregate.update({status.lower(): sum(x["match_status"] == status for x in results) for status in statuses})
    interpretation = "The event records do not reliably identify OSM segments unless a candidate has explicit reference or strong name evidence. Coordinate-only results remain review candidates or coordinate fallbacks; no fallback is represented as an OSM match."
    report = {"events": results, "aggregate": aggregate, "interpretation": interpretation, "limitations": ["Pilot remains limited to the first 10 eligible events.", "No OSM ID is fabricated or forced.", "No satellite labels or disruption model were changed."]}
    candidate_report = {"candidates": candidate_rows, "aggregate": aggregate, "interpretation": "All local-PBF highway candidates within 300 m are retained, including candidates rejected as non-road features or invalid geometry."}
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "osm_road_matching_results.json").write_text(json.dumps(report, indent=2, default=str))
    (REPORTS / "osm_candidate_audit.json").write_text(json.dumps(candidate_report, indent=2, default=str))
    result_columns = ["event_id", "road_name", "road_name_quality", "extracted_highway_ref", "match_status", "osm_way_id", "osm_road_name", "osm_ref", "distance_from_event", "nearest_candidate_distance", "second_nearest_candidate_distance", "distance_gap", "candidate_count", "match_reason", "geometry_review_overlay"]
    candidate_columns = ["event_id", "osm_way_id", "name", "ref", "highway", "distance_m", "geometry_valid", "name_similarity", "ref_match", "candidate_score", "rejection_reason"]
    (REPORTS / "osm_road_matching_results.md").write_text(_markdown("OSM road matching results", report, results, result_columns))
    (REPORTS / "osm_candidate_audit.md").write_text(_markdown("OSM candidate audit", candidate_report, candidate_rows, candidate_columns))
    return report


if __name__ == "__main__": print(json.dumps(run("--from-previous-audit" in __import__("sys").argv), indent=2, default=str))
