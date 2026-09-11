"""Phase 9C: resolve PWD road identity without fabricating geometry joins."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

from ..satellite_cv.road_geometry import match_local_pbf_events, road_identity

ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "data" / "reports"
PARQUET = ROOT / "data" / "processed" / "road_disruption" / "pwd_road_status_events.parquet"
RAW_DIR = ROOT / "data" / "raw" / "training" / "uttarakhand_pwd"

PUBLIC_SOURCES = [
    {
        "name": "PWD MIS road closure status list",
        "url": "https://mis.pwduk.in/pwd/roadClosureStatus",
        "result": "Structured public list sample; numeric PWD fields and HTML-linked segment-history IDs; no coordinates in list rows.",
    },
    {
        "name": "PWD MIS segment history for segment 5731",
        "url": "https://mis.pwduk.in/pwd/eeOfficeSegmentHistory/5731",
        "result": "Public HTML history; exposes KM, Closed On, Opened On, Open Type, lat, lng, and an IM segment-map link for road ID 19.",
    },
    {
        "name": "PWD IM segment map for road ID 19",
        "url": "https://mis.pwduk.in/im/segmentMap/19",
        "result": "Public HTML page returned 200; bounded inspection found no explicit latitude, longitude, GeoJSON, WKT, or polyline geometry field.",
    },
    {
        "name": "PWD IM GIS landing page",
        "url": "https://mis.pwduk.in/im/gis",
        "result": "Public HTML page returned 200; no structured authoritative road geometry or documented public identifier join was exposed in the bounded inspection.",
    },
    {
        "name": "PWD SRMD daily reports archive",
        "url": "https://pwd.uk.gov.in/document-category/srmd-daily-reports-2026/",
        "result": "Public PDF archive; authoritative documents may provide narrative evidence, but it is not a structured road-geometry identifier source for this sample.",
    },
    {
        "name": "OpenStreetMap local road geometry",
        "url": "https://www.openstreetmap.org/",
        "result": "Existing local conservative PBF matcher was used only for records with both strong road identity and coordinates; no record met both conditions.",
    },
]


def _identity_quality(row: dict[str, Any]) -> str:
    identity = road_identity(row)
    if identity["road_name_quality"] == "VALID" and pd.notna(row.get("latitude")) and pd.notna(row.get("longitude")):
        return "eligible"
    return "ineligible"


def resolve_identity() -> dict[str, Any]:
    frame = pd.read_parquet(PARQUET)
    rows = frame.to_dict("records")
    road_ids = sorted({str(value) for value in frame["road_id"].dropna()})
    segment_ids = sorted({str(value) for value in frame["segment_id"].dropna()})
    road_names = sorted({str(value) for value in frame["road_name"].dropna()})
    coordinate_rows = [row for row in rows if pd.notna(row.get("latitude")) and pd.notna(row.get("longitude"))]
    eligible = [
        {**row, "event_id": str(index)}
        for index, row in enumerate(rows)
        if _identity_quality(row) == "eligible"
    ]
    match_counts = {key: 0 for key in ("HIGH", "MEDIUM", "LOW", "AMBIGUOUS", "NO_RELIABLE_MATCH")}
    if eligible:
        matches = match_local_pbf_events(eligible)
        for result in matches.values():
            status = result.get("match_status", "NO_RELIABLE_MATCH")
            status = {"HIGH_CONFIDENCE": "HIGH", "MEDIUM_CONFIDENCE": "MEDIUM"}.get(status, status)
            match_counts[status if status in match_counts else "NO_RELIABLE_MATCH"] += 1
    match_counts["NO_RELIABLE_MATCH"] += len(rows) - len(eligible)
    unresolved_reasons = Counter()
    for row in rows:
        has_name = pd.notna(row.get("road_name")) and str(row.get("road_name")).strip()
        has_coords = pd.notna(row.get("latitude")) and pd.notna(row.get("longitude"))
        if not has_coords:
            unresolved_reasons["list records have no latitude/longitude"] += 1
        elif not has_name:
            unresolved_reasons["history coordinates have no normalized road_name"] += 1
        else:
            unresolved_reasons["no reliable local OSM candidate or authoritative geometry join"] += 1
    identity_quality = Counter(road_identity(row)["road_name_quality"] for row in rows)
    return {
        "report_title": "Phase 9C — Uttarakhand PWD road-identity resolution",
        "phase": "P3 Road Risk — Phase 9C",
        "input": {
            "normalized_file": str(PARQUET.relative_to(ROOT)),
            "raw_artifacts": sorted(path.name for path in RAW_DIR.iterdir() if path.is_file()),
            "records_attempted": len(rows),
        },
        "field_semantics": {
            "road_id": "Numeric PWD road identifier as observed in the public list; no public field dictionary or geometry join was found.",
            "segment_id": "Numeric PWD segment identifier in the list; the linked eeOfficeSegmentHistory URL contains a separate numeric history/segment identifier. Equality is observed for the sample but not independently documented as a geometry key.",
            "road_name": "HTML anchor text from the public list. Eight unique non-null names are present; several contain route descriptions and explicit NH text, but no exact OSM/PWD geometry key is supplied.",
            "road_km": "Comma-separated PWD KM marker IDs/values from the list, and individual KM values in history HTML; not a metric coordinate or geometry identifier by itself.",
            "district": "Numeric district_id only; no district name or public lookup mapping was present in the normalized sample.",
            "latitude_longitude": "Null on all list records; present on three history rows for segment 5731 only. These coordinates are not sufficient alone for a training identity join.",
        },
        "observed_values": {
            "road_ids": road_ids,
            "segment_ids": segment_ids,
            "unique_road_names": road_names,
            "unique_road_name_count": len(road_names),
            "coordinate_available_records": len(coordinate_rows),
            "coordinate_missing_records": len(rows) - len(coordinate_rows),
            "district_ids": sorted({str(value) for value in frame["district"].dropna()}),
            "road_name_identity_quality": dict(identity_quality),
        },
        "authoritative_identifiers_discovered": [
            "PWD road_id and segment_id values observed in the public MIS list",
            "PWD eeOfficeSegmentHistory/5731 public history identifier",
            "PWD IM segmentMap/19 public link associated with the sampled history page",
        ],
        "identity_sources_investigated": PUBLIC_SOURCES,
        "osm_matching": {
            "records_eligible_for_existing_conservative_matcher": len(eligible),
            "counts": match_counts,
            "coordinate_buffer_fallback_used_as_identity": False,
            "unresolved_records": len(rows),
            "reason": "No normalized record had both a sufficiently strong road identity and coordinates. The three coordinate-bearing history rows have no normalized road_name; list rows have names but no coordinates.",
        },
        "unresolved_records": len(rows),
        "unresolved_reasons": dict(unresolved_reasons),
        "reliable_road_geometry_available": False,
        "conclusion": "Phase 9C does not establish a usable road-geometry join. PWD identifiers are retained as source identifiers, not treated as OSM IDs or geometry keys. Do not proceed to satellite/CV or supervised disruption training from this sample.",
        "model_b_or_satellite_changes": False,
    }


def write_reports() -> dict[str, Path]:
    report = resolve_identity()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORT_DIR / "phase9c_pwd_identity_resolution.json"
    markdown_path = REPORT_DIR / "phase9c_pwd_identity_resolution.md"
    json_path.write_text(json.dumps(report, indent=2))
    markdown_path.write_text("\n".join([
        "# Phase 9C — Uttarakhand PWD road-identity resolution", "",
        f"- Records attempted: {report['input']['records_attempted']}",
        f"- Road IDs examined: {', '.join(report['observed_values']['road_ids'])}",
        f"- Segment IDs examined: {', '.join(report['observed_values']['segment_ids'])}",
        f"- Unique road names: {report['observed_values']['unique_road_name_count']}",
        f"- Coordinate-bearing records: {report['observed_values']['coordinate_available_records']}",
        f"- OSM matches: `{json.dumps(report['osm_matching']['counts'], sort_keys=True)}`",
        f"- Unresolved records: {report['unresolved_records']}",
        "", "## Sources investigated", "",
        *[f"- {source['name']}: {source['url']} — {source['result']}" for source in PUBLIC_SOURCES],
        "", "## Field semantics", "",
        *[f"- `{name}`: {description}" for name, description in report["field_semantics"].items()],
        "", "## Unresolved reasons", "",
        *[f"- {reason}: {count}" for reason, count in report["unresolved_reasons"].items()],
        "", report["conclusion"], "",
    ]))
    return {"json": json_path, "markdown": markdown_path}


if __name__ == "__main__":
    print(json.dumps(resolve_identity(), indent=2))
    write_reports()