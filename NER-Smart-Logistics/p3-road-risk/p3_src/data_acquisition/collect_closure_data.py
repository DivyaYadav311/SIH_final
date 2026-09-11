from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW_ROOT = ROOT / "data" / "raw" / "road_closure_evidence"
CACHE_ROOT = RAW_ROOT / "cache"
MANIFEST_ROOT = RAW_ROOT / "source_manifests"
PROCESSED_ROOT = ROOT / "data" / "processed" / "road_closure"
REPORT_ROOT = ROOT / "data" / "reports"
SOURCE_GEOJSON = ROOT / "data" / "raw" / "landslides" / "historical_landslides.geojson"
PIPELINE_VERSION = "road-closure-evidence-v1"

EVENT_COLUMNS = [
    "event_id", "road_name", "highway_number", "road_type", "state", "district", "city_or_town",
    "latitude", "longitude", "event_timestamp", "closure_start", "closure_end", "closure_status",
    "event_timestamp_type", "timestamp_confidence", "timestamp_source",
    "road_closed", "hazard_type", "closure_reason", "source_id", "source_type", "source_name",
    "source_publisher", "source_document", "source_url", "source_publication_date", "evidence_text",
    "extraction_confidence", "label_confidence",
    "osm_match_status", "osm_road_id", "source_count", "source_ids", "source_urls",
]

CLOSED_PATTERNS = [
    r"\broad\b[^.]{0,100}\bblocked\b",
    r"\bblocked\b[^.]{0,100}\broad\b",
    r"\broad\b[^.]{0,100}\bclosed\b",
    r"\bclosed\b[^.]{0,100}\broad\b",
    r"\bhighway\b[^.]{0,100}\b(blocked|closed)\b",
    r"\btraffic\b[^.]{0,100}\b(stopped|disrupted|suspended)\b",
    r"\b(vehicular movement|connectivity)\b[^.]{0,100}\b(stopped|disrupted|blocked)\b",
    r"\broad\b[^.]{0,100}\bwashed away\b",
    r"\broad\b[^.]{0,100}\binaccessible\b",
]
OPEN_PATTERNS = [
    r"\broad\b[^.]{0,100}\breopened\b",
    r"\broad\b[^.]{0,100}\bopened to traffic\b",
    r"\btraffic\b[^.]{0,100}\brestored\b",
    r"\bconnectivity\b[^.]{0,100}\brestored\b",
    r"\b(route|road)\b[^.]{0,100}\breopened\b",
    r"\bvehicular movement\b[^.]{0,100}\bresumed\b",
]
ROAD_TOKEN = re.compile(r"\b(road|highway|nh[- ]?\d+|national highway|traffic|vehicular|connectivity)\b", re.I)
HIGHWAY_PATTERN = re.compile(r"\b(?:NH|N\.H\.?|National Highway)\s*[- ]?\s*(\d+[A-Za-z]?)\b", re.I)
EXPLICIT_DATE_PATTERN = re.compile(
    r"\b(?:on\s+)?(\d{1,2})(?:st|nd|rd|th)?\s+"
    r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+"
    r"(20\d{2})\b", re.I
)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("ΓÇô", "-")).strip()


def normalize_road(value: str) -> str:
    value = normalize_text(value).lower()
    value = re.sub(r"\bn\.h\.?\s*[- ]?\s*", "nh-", value)
    value = re.sub(r"\bnational highway\s*[- ]?\s*", "nh-", value)
    value = re.sub(r"\bnh\s*[- ]?\s*", "nh-", value)
    return re.sub(r"[^a-z0-9-]+", " ", value).strip()


def evidence_sentence(text: str, patterns: list[str]) -> str | None:
    normalized = normalize_text(text)
    for pattern in patterns:
        match = re.search(pattern, normalized, re.I)
        if match:
            start = max(0, normalized.rfind(".", 0, match.start()) + 1)
            end = normalized.find(".", match.end())
            end = len(normalized) if end < 0 else end + 1
            return normalized[start:end].strip()[:500]
    return None


def infer_hazard(properties: dict[str, Any]) -> str | None:
    value = normalize_text(properties.get("TRIGGERING") or properties.get("GEOSCIENTIFIC_CAUSE"))
    if not value:
        return "landslide"
    lowered = value.lower()
    if "rain" in lowered:
        return "landslide_after_rainfall"
    if "flood" in lowered or "water" in lowered:
        return "flood_or_water"
    return "landslide"


def extract_event_date(properties: dict[str, Any]) -> tuple[str | None, str, str, str | None]:
    """Use only an explicit narrative date; never infer from opaque IDs or filenames."""
    abstract = normalize_text(properties.get("ABSTRACT"))
    match = EXPLICIT_DATE_PATTERN.search(abstract)
    if not match:
        return None, "unknown", "unknown", None
    try:
        parsed = datetime.strptime(
            f"{match.group(1)} {match.group(2)} {match.group(3)}", "%d %B %Y"
        )
    except ValueError:
        return None, "unknown", "unknown", None
    return parsed.date().isoformat(), "event_date", "high", "ABSTRACT"


def source_manifest() -> dict[str, Any]:
    MANIFEST_ROOT.mkdir(parents=True, exist_ok=True)
    try:
        local_path = str(SOURCE_GEOJSON.relative_to(ROOT))
    except ValueError:
        local_path = str(SOURCE_GEOJSON)
    try:
        cache_path = str(CACHE_ROOT.relative_to(ROOT))
    except ValueError:
        cache_path = str(CACHE_ROOT)
    sources = [
        {
            "source_id": "nrsc_historical_landslides_local",
            "source_name": "Historical landslide inventory local GeoJSON",
            "publisher": "Unknown; local inventory provenance not supplied",
            "source_type": "official_inventory_local_cache",
            "source_url": "unknown",
            "jurisdiction": "India",
            "date_range": "unknown; source has no event date field",
            "acquisition_method": "existing local file; no download",
            "license_or_access_notes": "Source provenance/license URL was not supplied; verify before redistribution.",
            "enabled": True,
            "last_attempted": now(),
            "status": "available_local",
            "local_path": local_path,
        },
        {
            "source_id": "asdma_public_reports",
            "source_name": "ASDMA public report discovery",
            "publisher": "ASDMA",
            "source_type": "government_reports",
            "source_url": "https://asdma.assam.gov.in/",
            "jurisdiction": "Assam, India",
            "date_range": "unknown",
            "acquisition_method": "existing manifest/cache; network acquisition deferred",
            "license_or_access_notes": "Public website; obey site access policy.",
            "enabled": False,
            "last_attempted": None,
            "status": "discovered_but_no_valid_closure_document_cached",
            "local_path": "data/raw/incidents/asdma/manifest.csv",
        },
        {
            "source_id": "gdelt_historical_news",
            "source_name": "GDELT historical news discovery",
            "publisher": "GDELT Project",
            "source_type": "news_api",
            "source_url": "https://api.gdeltproject.org/api/v2/doc/doc",
            "jurisdiction": "India",
            "date_range": "2022-2025 intended",
            "acquisition_method": "public API; rate-limited and not used without cached raw response",
            "license_or_access_notes": "Public API; no authentication bypass; rate limits apply.",
            "enabled": False,
            "last_attempted": None,
            "status": "not_run_no_cache",
            "local_path": cache_path,
        },
    ]
    for source in sources:
        source.setdefault("accessed_at", source.get("last_attempted"))
        source.setdefault("coverage_period", source.get("date_range"))
        source.setdefault("records_found", 0)
        source.setdefault("records_extracted", 0)
        source.setdefault("positive_records", 0)
        source.setdefault("negative_records", 0)
        source.setdefault("timestamped_records", 0)
        source.setdefault("notes", source.get("status"))
    payload = {"pipeline_version": PIPELINE_VERSION, "generated_at": now(), "sources": sources}
    (MANIFEST_ROOT / "sources.json").write_text(json.dumps(payload, indent=2))
    (REPORT_ROOT / "road_closure_sources.json").write_text(json.dumps(payload, indent=2))
    return payload


def read_inventory() -> list[dict[str, Any]]:
    if not SOURCE_GEOJSON.exists():
        return []
    payload = json.loads(SOURCE_GEOJSON.read_text())
    records = []
    for index, feature in enumerate(payload.get("features", [])):
        properties = feature.get("properties") or {}
        geometry = feature.get("geometry") or {}
        coords = geometry.get("coordinates") or []
        try:
            longitude = float(properties.get("LONGITUDE", coords[0]))
            latitude = float(properties.get("LATITUDE", coords[1]))
        except (TypeError, ValueError, IndexError):
            longitude = latitude = None
        communication = normalize_text(properties.get("COMMUNICATION_AFFECTED"))
        infrastructure = normalize_text(properties.get("INFRASTRUCTURE_AFFECTED"))
        context = " ".join(value for value in [communication, infrastructure] if value)
        closed = evidence_sentence(context, CLOSED_PATTERNS)
        opened = evidence_sentence(context, OPEN_PATTERNS)
        road_value = normalize_text(properties.get("NH_SH_LOCATION"))
        if not road_value and closed:
            road_value = closed
        if not ROAD_TOKEN.search(context + " " + road_value):
            continue
        event_timestamp, timestamp_type, timestamp_confidence, timestamp_source = extract_event_date(properties)
        if closed:
            status, label, confidence, evidence = "closed", 1, "high", closed
        elif opened:
            status, label, confidence, evidence = "open", 0, "high", opened
        else:
            status, label, confidence, evidence = "unknown", None, "low", normalize_text(context)[:500] or None
        highway = HIGHWAY_PATTERN.search(road_value + " " + context)
        highway_number = f"NH-{highway.group(1).upper()}" if highway else None
        record = {
            "source_record_id": str(properties.get("OBJECTID") or properties.get("SLIDE_NO") or index),
            "road_name": road_value or None,
            "highway_number": highway_number,
            "road_type": "highway" if highway_number else "road",
            "state": normalize_text(properties.get("STATE")) or None,
            "district": normalize_text(properties.get("DISTRICT")) or None,
            "city_or_town": normalize_text(properties.get("SLIDE_NAME")) or None,
            "latitude": latitude,
            "longitude": longitude,
            "event_timestamp": event_timestamp,
            "closure_start": None,
            "closure_end": None,
            "event_timestamp_type": timestamp_type,
            "timestamp_confidence": timestamp_confidence,
            "timestamp_source": timestamp_source,
            "closure_status": status,
            "road_closed": label,
            "hazard_type": infer_hazard(properties),
            "closure_reason": normalize_text(properties.get("GEOSCIENTIFIC_CAUSE")) or None,
            "source_id": "nrsc_historical_landslides_local",
            "source_type": "official_inventory_local_cache",
            "source_name": "Historical landslide inventory local GeoJSON",
            "source_publisher": "Unknown; local inventory provenance not supplied",
            "source_document": SOURCE_GEOJSON.name,
            "source_url": "unknown",
            "source_publication_date": None,
            "evidence_text": evidence,
            "extraction_confidence": confidence,
            "label_confidence": confidence if label is not None else "unknown",
            "osm_match_status": "not_attempted_no_road_index",
            "osm_road_id": None,
        }
        records.append(record)
    return records


def inventory_record_count() -> int:
    if not SOURCE_GEOJSON.exists():
        return 0
    payload = json.loads(SOURCE_GEOJSON.read_text())
    return len(payload.get("features", []))


def deduplicate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for record in records:
        key = (
            normalize_road(record.get("road_name") or ""),
            normalize_text(record.get("state") or "").lower(),
            normalize_text(record.get("district") or "").lower(),
            record.get("latitude"), record.get("longitude"),
            record.get("closure_status"), record.get("evidence_text"),
        )
        groups.setdefault(key, []).append(record)
    output = []
    for members in groups.values():
        first = dict(members[0])
        first["event_id"] = hashlib.sha256("|".join(str(first.get(key) or "") for key in ["source_id", "source_record_id", "road_name", "state", "district", "evidence_text"]).encode()).hexdigest()[:20]
        first["source_count"] = len({member["source_id"] for member in members})
        first["source_ids"] = json.dumps(sorted({member["source_id"] for member in members}))
        first["source_urls"] = json.dumps(sorted({member["source_url"] for member in members}))
        output.append(first)
    return output


def write_reports(source_record_count: int, raw_records: list[dict[str, Any]], events: pd.DataFrame) -> None:
    accepted = events[events.road_closed.notna()] if not events.empty else events
    report = {
        "pipeline_version": PIPELINE_VERSION,
        "generated_at": now(),
        "source_records_examined": source_record_count,
        "extracted_records": len(raw_records),
        "unique_events": len(events),
        "closed_events": int((events.road_closed == 1).sum()) if not events.empty else 0,
        "open_events": int((events.road_closed == 0).sum()) if not events.empty else 0,
        "unknown_events": int(events.road_closed.isna().sum()) if not events.empty else 0,
        "rejected_records": max(0, source_record_count - len(raw_records)),
        "unique_roads": int(events.road_name.dropna().map(normalize_road).nunique()) if not events.empty else 0,
        "unique_highways": int(events.highway_number.dropna().nunique()) if not events.empty else 0,
        "unique_states": int(events.state.dropna().nunique()) if not events.empty else 0,
        "unique_districts": int(events.district.dropna().nunique()) if not events.empty else 0,
        "date_range": {
            "min": str(events.event_timestamp.dropna().min()) if not events.empty and events.event_timestamp.notna().any() else None,
            "max": str(events.event_timestamp.dropna().max()) if not events.empty and events.event_timestamp.notna().any() else None,
        },
        "timestamp_types": events.event_timestamp_type.value_counts(dropna=False).to_dict() if not events.empty else {},
        "by_state": events.state.value_counts(dropna=False).to_dict() if not events.empty else {},
        "by_hazard": events.hazard_type.value_counts(dropna=False).to_dict() if not events.empty else {},
        "by_source": events.source_id.value_counts(dropna=False).to_dict() if not events.empty else {},
        "by_label_confidence": events.label_confidence.value_counts(dropna=False).to_dict() if not events.empty else {},
        "coordinate_percentage": float(events[["latitude", "longitude"]].notna().all(axis=1).mean() * 100) if not events.empty else 0.0,
        "road_name_percentage": float(events.road_name.notna().mean() * 100) if not events.empty else 0.0,
        "timestamp_percentage": float(events.event_timestamp.notna().mean() * 100) if not events.empty else 0.0,
        "evidence_percentage": float(events.evidence_text.notna().mean() * 100) if not events.empty else 0.0,
        "modeling_status": "insufficient_binary_labels_without explicit open evidence or event timestamps",
    }
    (REPORT_ROOT / "road_closure_extraction_report.json").write_text(json.dumps(report, indent=2, default=str))
    label_audit = {
        "closed_label_rule": "explicit road/highway blocked/closed/disrupted evidence only",
        "open_label_rule": "explicit road reopened/opened/traffic restored evidence only",
        "unknown_policy": "retained in events, excluded from binary training",
        "closed_examples": accepted[accepted.road_closed == 1].head(5)[["event_id", "road_name", "state", "evidence_text"]].to_dict("records") if not accepted.empty else [],
        "open_examples": [],
        "unknown_examples": events[events.road_closed.isna()].head(5)[["event_id", "road_name", "state", "evidence_text"]].to_dict("records") if not events.empty else [],
        "disaster_road_disruption_target": "UNAVAILABLE_FOR_MODELING" if events.empty or events.road_closed.dropna().nunique() < 2 else "AVAILABLE_PENDING_TEMPORAL_VALIDATION",
    }
    (REPORT_ROOT / "road_closure_label_audit.json").write_text(json.dumps(label_audit, indent=2, default=str))
    (REPORT_ROOT / "road_closure_negative_label_audit.md").write_text(
        f"# Negative-label audit\n\n"
        f"- Total records: {len(events)}\n"
        f"- Explicit closed records: {report['closed_events']}\n"
        f"- Explicit open/reopened records: {report['open_events']}\n"
        f"- Dated closed records: {int(((events.road_closed == 1) & events.event_timestamp.notna()).sum()) if not events.empty else 0}\n"
        f"- Dated open/reopened records: {int(((events.road_closed == 0) & events.event_timestamp.notna()).sum()) if not events.empty else 0}\n"
        f"- Rejected negative candidates: no silence, hazard absence, or random observations were converted to 0.\n\n"
        "Model B remains untrainable because no explicit dated opening evidence was acquired.\n"
    )
    temporal_audit = {
        "source_has_explicit_event_dates": bool(not events.empty and events.event_timestamp.notna().any()),
        "timestamp_types": events.event_timestamp_type.value_counts(dropna=False).to_dict() if not events.empty else {},
        "timestamp_confidence": events.timestamp_confidence.value_counts(dropna=False).to_dict() if not events.empty else {},
        "event_timestamp_rows": int(events.event_timestamp.notna().sum()) if not events.empty else 0,
        "report_date_rows": int((events.event_timestamp_type == "report_date").sum()) if not events.empty else 0,
        "publication_date_rows": int((events.event_timestamp_type == "publication_date").sum()) if not events.empty else 0,
        "unknown_timestamp_rows": int((events.event_timestamp_type == "unknown").sum()) if not events.empty else 0,
        "timestamp_rule": "Only explicit calendar dates in ABSTRACT are used; INITIATION, filenames, mtime, and report metadata are not promoted to event timestamps.",
        "usable_for_chronological_model": False,
        "reason": "No explicit open/reopened labels; recovered dates are narrative event dates and closure/open classes remain incomplete.",
    }
    (REPORT_ROOT / "road_closure_temporal_audit.json").write_text(json.dumps(temporal_audit, indent=2, default=str))
    (REPORT_ROOT / "road_closure_temporal_audit.md").write_text(
        "# Temporal audit\n\n" + json.dumps(temporal_audit, indent=2, default=str)
    )
    negative_audit = {
        "explicit_open_events": int((events.road_closed == 0).sum()) if not events.empty else 0,
        "negative_label_rule": "Only explicit reopened/opened/traffic-restored evidence may produce road_closed=0.",
        "absence_converted_to_negative": False,
        "hazard_or_proximity_converted_to_negative": False,
        "status": "insufficient_explicit_open_evidence",
    }
    negative_audit.update({
        "total_records": len(events),
        "closed_records": int((events.road_closed == 1).sum()) if not events.empty else 0,
        "dated_closed_records": int(((events.road_closed == 1) & events.event_timestamp.notna()).sum()) if not events.empty else 0,
        "dated_open_records": int(((events.road_closed == 0) & events.event_timestamp.notna()).sum()) if not events.empty else 0,
        "duplicate_count": int(len(events) - events.event_id.nunique()) if not events.empty else 0,
        "source_wise_negative_counts": events[events.road_closed == 0].groupby("source_id").size().to_dict() if not events.empty else {},
        "state_wise_negative_counts": events[events.road_closed == 0].groupby("state").size().to_dict() if not events.empty else {},
        "rejected_negative_candidates": "All candidates without explicit opening/restoration evidence.",
    })
    (REPORT_ROOT / "road_closure_negative_label_audit.json").write_text(json.dumps(negative_audit, indent=2, default=str))
    summary = f"""# Road-closure evidence dataset report

## Acquisition
- Source records examined: {report['source_records_examined']}
- Extracted normalized records: {report['extracted_records']}
- Unique deduplicated events: {report['unique_events']}
- Source: local historical landslide inventory; source URL is unknown and remains explicitly unknown.

## Labels
- Closed: {report['closed_events']}
- Open: {report['open_events']}
- Unknown: {report['unknown_events']}
- Unknown records remain in the consolidated dataset and are excluded from binary training.
- No negative labels were created from absence of evidence.

## Coverage
- States: {report['unique_states']}
- Roads: {report['unique_roads']}
- Highways: {report['unique_highways']}
- Districts: {report['unique_districts']}
- Coordinates present: {report['coordinate_percentage']:.2f}%
- Explicit evidence present: {report['evidence_percentage']:.2f}%
- Event timestamps present: {report['timestamp_percentage']:.2f}%
- Timestamp types: {json.dumps(report['timestamp_types'], sort_keys=True)}

## Model status
A road-closure model was not trained. The source contains explicit positive road-blockage evidence and {int(events.event_timestamp.notna().sum()) if not events.empty else 0} narrative event dates, but no explicit open/reopened labels. Training a binary chronological model would require fabricated negatives. `disruption_probability` remains unavailable.

## Reproduction
`python -m src.data_acquisition.collect_closure_data`
"""
    (REPORT_ROOT / "road_closure_dataset_report.md").write_text(summary)
    model_status = {"status": "not_trained", "road_disruption_model_status": "insufficient_labels", "reason": "no defensible dated open labels", "disruption_probability_available": False}
    (REPORT_ROOT / "road_closure_model_evaluation.json").write_text(json.dumps(model_status, indent=2))
    (REPORT_ROOT / "model_evaluation_status.json").write_text(json.dumps(model_status, indent=2))
    (REPORT_ROOT / "model_evaluation_status.md").write_text("# Model evaluation status\n\nModel B was NOT trained because explicit dated open/reopened evidence is unavailable.\n")
    dataset_report = dict(report)
    dataset_report.update({"road_disruption_model_status": "insufficient_labels", "disruption_probability_available": False})
    (REPORT_ROOT / "road_closure_dataset_report.json").write_text(json.dumps(dataset_report, indent=2, default=str))


def update_final_pipeline_report(events: pd.DataFrame, source_record_count: int) -> None:
    report_path = REPORT_ROOT / "final_pipeline_report.md"
    existing = report_path.read_text() if report_path.exists() else "# Final P3 pipeline report\n"
    marker = "\n## Phase 3 road-closure evidence\n"
    existing = existing.split(marker, 1)[0]
    closed = int((events.road_closed == 1).sum()) if not events.empty else 0
    opened = int((events.road_closed == 0).sum()) if not events.empty else 0
    unknown = int(events.road_closed.isna().sum()) if not events.empty else 0
    section = f"""{marker}
- Source records examined: {source_record_count}
- Unique normalized events: {len(events)}
- Explicit closed events: {closed}
- Explicit open events: {opened}
- Unknown events retained: {unknown}
- Source states: {events.state.dropna().nunique() if not events.empty else 0}
- Source event timestamps: {events.event_timestamp.notna().sum() if not events.empty else 0}
- Model B status: UNAVAILABLE. No explicit open labels or event timestamps exist for a defensible chronological binary model.
- `disruption_probability`: remains `null`.
- Reproduce with: `python -m src.data_acquisition.collect_closure_data --force`
"""
    report_path.write_text(existing.rstrip() + "\n" + section)


def update_source_coverage(events: pd.DataFrame, source_record_count: int, extracted_count: int) -> None:
    source_counts = {
        "nrsc_historical_landslides_local": {
            "records_found": source_record_count,
            "records_extracted": extracted_count,
            "positive_records": int((events.road_closed == 1).sum()) if not events.empty else 0,
            "negative_records": int((events.road_closed == 0).sum()) if not events.empty else 0,
            "timestamped_records": int(events.event_timestamp.notna().sum()) if not events.empty else 0,
            "notes": "Only explicit narrative dates were recovered; no open records found.",
        },
        "asdma_public_reports": {
            "records_found": 0, "records_extracted": 0, "positive_records": 0,
            "negative_records": 0, "timestamped_records": 0,
            "notes": "Existing manifest/cache contained no validated dated road-status record.",
        },
        "gdelt_historical_news": {
            "records_found": 0, "records_extracted": 0, "positive_records": 0,
            "negative_records": 0, "timestamped_records": 0,
            "notes": "Not acquired in this run; public API rate limits and no cached response.",
        },
    }
    coverage = {"generated_at": now(), "sources": source_counts}
    (REPORT_ROOT / "road_closure_source_coverage.json").write_text(json.dumps(coverage, indent=2))
    lines = ["# Road-closure source coverage", ""]
    for source_id, values in source_counts.items():
        lines += [f"## {source_id}", "", f"- Records found: {values['records_found']}", f"- Records extracted: {values['records_extracted']}", f"- Positive records: {values['positive_records']}", f"- Negative records: {values['negative_records']}", f"- Timestamped records: {values['timestamped_records']}", f"- Notes: {values['notes']}", ""]
    (REPORT_ROOT / "road_closure_source_coverage.md").write_text("\n".join(lines))

    manifest_path = MANIFEST_ROOT / "sources.json"
    payload = json.loads(manifest_path.read_text())
    for source in payload.get("sources", []):
        source.update(source_counts.get(source["source_id"], {}))
    manifest_path.write_text(json.dumps(payload, indent=2))
    (REPORT_ROOT / "road_closure_sources.json").write_text(json.dumps(payload, indent=2))


def collect(force: bool = False) -> dict[str, Any]:
    for path in [CACHE_ROOT, MANIFEST_ROOT, PROCESSED_ROOT, REPORT_ROOT]:
        path.mkdir(parents=True, exist_ok=True)
    source_manifest()
    if force or not (PROCESSED_ROOT / "road_closure_events.parquet").exists():
        raw_records = read_inventory()
        events = pd.DataFrame(deduplicate(raw_records), columns=EVENT_COLUMNS[:-3] + ["source_count", "source_ids", "source_urls"])
        if events.empty:
            events = pd.DataFrame(columns=EVENT_COLUMNS)
        events.to_parquet(PROCESSED_ROOT / "road_closure_events.parquet", index=False)
        events.to_csv(PROCESSED_ROOT / "road_closure_events.csv", index=False)
    else:
        events = pd.read_parquet(PROCESSED_ROOT / "road_closure_events.parquet")
        raw_records = read_inventory()
    source_record_count = inventory_record_count()
    write_reports(source_record_count, raw_records, events)
    update_source_coverage(events, source_record_count, len(raw_records))
    update_final_pipeline_report(events, source_record_count)
    return {
        "source_records_examined": source_record_count,
        "unique_events": len(events),
        "closed_events": int((events.road_closed == 1).sum()) if not events.empty else 0,
        "open_events": int((events.road_closed == 0).sum()) if not events.empty else 0,
        "unknown_events": int(events.road_closed.isna().sum()) if not events.empty else 0,
        "model_trained": False,
        "disruption_probability_available": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect real historical road-closure evidence")
    parser.add_argument("--force", action="store_true", help="rebuild normalized evidence outputs")
    print(json.dumps(collect(force=parser.parse_args().force), indent=2))


if __name__ == "__main__":
    main()
