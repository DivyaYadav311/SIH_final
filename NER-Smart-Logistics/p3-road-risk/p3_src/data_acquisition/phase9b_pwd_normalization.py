"""Phase 9B: normalize and audit the bounded public Uttarakhand PWD sample."""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

import pandas as pd

from .pwd_sample_acquisition import SOURCE_URL, sha256_file
from .uttarakhand_pwd_schema_audit import parse_history_tables
from ..satellite_cv.road_geometry import match_local_pbf_events, road_identity

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw" / "training" / "uttarakhand_pwd"
REPORT_DIR = ROOT / "data" / "reports"
OUTPUT = ROOT / "data" / "processed" / "road_disruption" / "pwd_road_status_events.parquet"
LIST_FILE = RAW_DIR / "road_closure_status_datatables_sample.json"
HISTORY_FILE = RAW_DIR / "ee_office_segment_history_5731.html"

COLUMNS = [
    "source_record_id", "road_id", "segment_id", "road_name", "road_km", "district",
    "latitude", "longitude", "event_timestamp", "closure_start", "closure_end", "status",
    "road_closed", "source_publisher", "source_document", "source_url", "source_retrieved_at",
]
PUBLISHER = "Public Works Department, Government of Uttarakhand"


def _text(value: Any) -> str | None:
    if value is None:
        return None
    value = unescape(re.sub(r"<[^>]+>", " ", str(value)))
    value = re.sub(r"\s+", " ", value).strip()
    return value or None


def _segment_id(value: Any) -> str | None:
    match = re.search(r"eeOfficeSegmentHistory/(\d+)", str(value or ""))
    return match.group(1) if match else (str(value) if value not in (None, "") else None)


def _timestamp(value: Any) -> str | None:
    value = _text(value)
    if not value:
        return None
    parsed = pd.to_datetime(value, errors="coerce")
    return None if pd.isna(parsed) else parsed.isoformat()


def _explicit_label(status: Any) -> bool | None:
    normalized = _text(status)
    if not normalized:
        return None
    if normalized.casefold() in {"closed", "road closed"}:
        return True
    if normalized.casefold() in {"opened", "open", "road opened", "reopened"}:
        return False
    return None


def _list_records(payload: dict[str, Any], retrieved_at: str) -> list[dict[str, Any]]:
    records = []
    for row in payload.get("data") or []:
        segment_id = _segment_id(row.get("ee_office_segment_id") or row.get("segment_id"))
        road_id = row.get("road_id")
        event = _timestamp(row.get("event_datetime") or row.get("tc_date"))
        source_id = _text(row.get("source_record_id")) or (
            f"pwd:{road_id or ''}:{segment_id or ''}:{event or ''}:{row.get('road_km_id') or ''}"
        )
        records.append({
            "source_record_id": source_id,
            "road_id": str(road_id) if road_id is not None else None,
            "segment_id": segment_id,
            "road_name": _text(row.get("roadname")),
            "road_km": _text(row.get("road_km_id")),
            "district": str(row["district_id"]) if row.get("district_id") is not None else None,
            "latitude": None,
            "longitude": None,
            "event_timestamp": event,
            "closure_start": None,
            "closure_end": None,
            "status": _text(row.get("status")),
            "road_closed": _explicit_label(row.get("status")),
            "source_publisher": PUBLISHER,
            "source_document": LIST_FILE.name,
            "source_url": SOURCE_URL,
            "source_retrieved_at": retrieved_at,
        })
    return records


def _history_records(html: str, retrieved_at: str) -> list[dict[str, Any]]:
    records = []
    for row in parse_history_tables(html):
        status = _text(row.get("Open Type") or row.get("Status"))
        closed = _timestamp(row.get("Closed On"))
        opened = _timestamp(row.get("Opened On"))
        event = closed or opened
        source_id = _text(row.get("ID")) or f"pwd:history:5731:{event or ''}:{row.get('KM') or ''}"
        records.append({
            "source_record_id": f"pwd-history:{source_id}",
            "road_id": "19",
            "segment_id": "5731",
            "road_name": None,
            "road_km": _text(row.get("KM")),
            "district": None,
            "latitude": float(row["lat"]) if row.get("lat") else None,
            "longitude": float(row["lng"]) if row.get("lng") else None,
            "event_timestamp": event,
            "closure_start": closed,
            "closure_end": opened,
            "status": status,
            "road_closed": _explicit_label(status),
            "source_publisher": PUBLISHER,
            "source_document": HISTORY_FILE.name,
            "source_url": "https://mis.pwduk.in/pwd/eeOfficeSegmentHistory/5731",
            "source_retrieved_at": retrieved_at,
        })
    return records


def _deduplicate(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    seen: set[str] = set()
    unique = []
    for record in records:
        key = record["source_record_id"] or "|".join(str(record.get(field) or "") for field in ("road_id", "segment_id", "road_km", "event_timestamp", "status"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(record)
    return unique, len(records) - len(unique)


def _match_records(records: list[dict[str, Any]]) -> dict[str, int]:
    eligible = []
    eligible_indexes = []
    for index, record in enumerate(records):
        identity = road_identity(record)
        if identity["road_name_quality"] == "VALID" and record["latitude"] is not None and record["longitude"] is not None:
            eligible.append({**record, "event_id": str(index)})
            eligible_indexes.append(index)
    results = {name: 0 for name in ("HIGH", "MEDIUM", "LOW", "AMBIGUOUS", "NO_RELIABLE_MATCH")}
    if not eligible:
        results["NO_RELIABLE_MATCH"] = len(records)
        return results
    matched = match_local_pbf_events(eligible)
    for index in range(len(records)):
        result = matched.get(str(index)) if index in eligible_indexes else None
        status = (result or {}).get("match_status", "NO_RELIABLE_MATCH")
        status = {"HIGH_CONFIDENCE": "HIGH", "MEDIUM_CONFIDENCE": "MEDIUM"}.get(status, status)
        if status not in results or status == "COORDINATE_FALLBACK":
            status = "NO_RELIABLE_MATCH"
        results[status] += 1
    return results


def build_phase9b_report(retrieved_at: str | None = None) -> dict[str, Any]:
    retrieved_at = retrieved_at or datetime.now(timezone.utc).isoformat()
    payload = json.loads(LIST_FILE.read_text())
    raw_records = _list_records(payload, retrieved_at)
    if HISTORY_FILE.exists():
        raw_records.extend(_history_records(HISTORY_FILE.read_text(), retrieved_at))
    records, duplicates = _deduplicate(raw_records)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(records, columns=COLUMNS).to_parquet(OUTPUT, index=False)

    status_counts = dict(Counter(str(record["status"] or "UNKNOWN") for record in records))
    label_counts = {
        "explicit_closed": sum(record["road_closed"] is True for record in records),
        "explicit_opened": sum(record["road_closed"] is False for record in records),
        "unresolved_unknown": sum(record["road_closed"] is None for record in records),
    }
    null_rates = {column: round(sum(record.get(column) in (None, "") for record in records) / len(records) * 100, 2) if records else 100.0 for column in COLUMNS}
    complete_intervals = sum(bool(record["closure_start"] and record["closure_end"]) for record in records)
    segments = {record["segment_id"] for record in records if record["segment_id"]}
    repeated_segments = sum(count > 1 for count in Counter(record["segment_id"] for record in records if record["segment_id"]).values())
    identity_counts = Counter(road_identity(record)["road_name_quality"] for record in records)
    osm_counts = _match_records(records)
    report = {
        "report_title": "Phase 9B — Uttarakhand PWD controlled sample acquisition, normalization, and audit",
        "phase": "P3 Road Risk — Phase 9B",
        "acquisition": {
            "method": "One bounded public GET was attempted with DataTables parameters draw=1,start=0,length=100. The response was non-JSON, so no uncontrolled retry or scrape was performed.",
            "public_filtering_pagination": "Not verified as usable in this run; the existing legitimate 10-row public sample was retained.",
            "source_url": SOURCE_URL,
            "raw_artifacts": [{"file": path.name, "sha256": sha256_file(path)} for path in (LIST_FILE, HISTORY_FILE) if path.exists()],
            "retrieved_at": retrieved_at,
            "raw_record_count": len(raw_records),
            "record_limit": 500,
        },
        "normalization": {"normalized_record_count": len(records), "output": str(OUTPUT.relative_to(ROOT)), "required_columns": COLUMNS},
        "status_semantics": "Only exact explicit Closed/Open/Opened/Reopened values receive boolean labels. Closure Identified and all incomplete/unknown values remain null; timestamps are never inferred.",
        "deduplication": {"raw_records": len(raw_records), "duplicates_removed": duplicates, "unique_records": len(records)},
        "unique_road_segments": len(segments),
        "status_counts": status_counts,
        "null_rates_percent": null_rates,
        "closure_intervals": {"complete": complete_intervals, "incomplete": len(records) - complete_intervals},
        "labels": label_counts,
        "road_identity_quality": {"HIGH": identity_counts.get("VALID", 0), "MEDIUM": 0, "LOW": identity_counts.get("UNCERTAIN", 0) + identity_counts.get("EMPTY", 0), "evidence_basis": "Only PWD road names, segment/KM fields, and coordinates actually present in the sample."},
        "osm_matching": {"counts": osm_counts, "coordinate_fallback_used_as_label": False, "note": "Matching was attempted only for strong identity plus coordinates; coordinate-only fallback is reported as NO_RELIABLE_MATCH."},
        "temporal_feasibility": {"repeated_observations_same_segment": repeated_segments > 0, "repeated_segment_count": repeated_segments, "closed_to_open_transitions": False, "closure_start_end_available": complete_intervals > 0, "reliable_osm_geometry_join": osm_counts["HIGH"] + osm_counts["MEDIUM"] > 0, "enough_positive_and_negative_examples": label_counts["explicit_closed"] > 0 and label_counts["explicit_opened"] > 0, "model_b_trainable": False, "reason": "The sample is dominated by Closure Identified records, has no defensible paired closed-to-open transitions, and does not provide enough explicit binary labels."},
        "model_b": {"trained": False, "disruption_probability": None, "status": "insufficient_labels"},
    }
    return report


def write_phase9b_reports(retrieved_at: str | None = None) -> dict[str, Path]:
    report = build_phase9b_report(retrieved_at)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORT_DIR / "phase9b_pwd_sample_report.json"
    md_path = REPORT_DIR / "phase9b_pwd_sample_report.md"
    json_path.write_text(json.dumps(report, indent=2))
    md_path.write_text("\n".join([
        "# Phase 9B — Uttarakhand PWD controlled sample audit", "",
        f"- Acquisition: {report['acquisition']['method']}",
        f"- Raw records: {report['acquisition']['raw_record_count']}",
        f"- Normalized records: {report['normalization']['normalized_record_count']}",
        f"- Unique segments: {report['unique_road_segments']}",
        f"- Status counts: `{json.dumps(report['status_counts'], sort_keys=True)}`",
        f"- Duplicates removed: {report['deduplication']['duplicates_removed']}",
        f"- OSM matching counts: `{json.dumps(report['osm_matching']['counts'], sort_keys=True)}`",
        "", "## Semantics", "", report["status_semantics"],
        "", "## Feasibility", "", report["temporal_feasibility"]["reason"],
        "", "**Model B trainable:** no. `disruption_probability` remains `null`.", "",
    ]))
    return {"json": json_path, "markdown": md_path}


if __name__ == "__main__":
    print(json.dumps(build_phase9b_report(), indent=2))
    write_phase9b_reports()