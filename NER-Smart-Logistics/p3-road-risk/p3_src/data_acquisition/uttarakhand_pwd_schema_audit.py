"""Phase 9A: audit a saved Uttarakhand PWD sample without inventing fields or labels."""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw" / "training" / "uttarakhand_pwd"
REPORT_DIR = ROOT / "data" / "reports"
LIST_SAMPLE = RAW_DIR / "road_closure_status_datatables_sample.json"
HISTORY_SAMPLE = RAW_DIR / "ee_office_segment_history_5731.html"
MANIFEST_PATH = RAW_DIR / "source_manifest.json"

SOURCE_NAME = "Uttarakhand PWD Road Closure Status MIS"
PUBLISHER = "Public Works Department, Government of Uttarakhand"
SOURCE_URL = "https://mis.pwduk.in/pwd/roadClosureStatus"
SRMD_URL = "https://pwd.uk.gov.in/document-category/srmd-daily-reports-2026/"
SRMD_PAGE_URL = "https://pwd.uk.gov.in/srmd-reports/"
LOGIN_URL = "https://mis.pwduk.in/pwd/login"
GEOGRAPHIC_SCOPE = "Uttarakhand, India — PWD-managed roads visible in the public MIS date-filtered view"

REQUESTED_FIELDS = [
    "road_name",
    "road_number",
    "highway_number",
    "road_segment",
    "km_marker",
    "district",
    "latitude",
    "longitude",
    "event_date",
    "event_time",
    "closure_start",
    "closure_end",
    "closure_status",
    "reason",
    "hazard_type",
    "source_record_id",
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def strip_html(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = unescape(re.sub(r"<[^>]+>", " ", value))
    return re.sub(r"\s+", " ", text).strip()


def is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and strip_html(value) == "":
        return True
    return False


def null_pct(rows: list[dict[str, Any]], field: str) -> float:
    if not rows:
        return 100.0
    missing = sum(1 for row in rows if is_empty(row.get(field)))
    return round(100.0 * missing / len(rows), 2)


class HTMLTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tables: list[list[list[str]]] = []
        self._table: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self._skip += 1
            return
        if self._skip:
            return
        if tag == "table":
            self._table = []
            self.tables.append(self._table)
        elif tag == "tr" and self._table is not None:
            self._row = []
            self._table.append(self._row)
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = []
        elif tag == "br" and self._cell is not None:
            self._cell.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self._skip = max(0, self._skip - 1)
            return
        if self._skip:
            return
        if tag in {"td", "th"} and self._cell is not None and self._row is not None:
            self._row.append(unescape(re.sub(r"\s+", " ", "".join(self._cell))).strip())
            self._cell = None
        elif tag == "table":
            self._table = None
            self._row = None

    def handle_data(self, data: str) -> None:
        if self._skip or self._cell is None:
            return
        self._cell.append(data)


def parse_history_tables(html: str) -> list[dict[str, str]]:
    parser = HTMLTableParser()
    parser.feed(html)
    if not parser.tables:
        return []
    header_row = parser.tables[0][0] if parser.tables[0] else []
    records: list[dict[str, str]] = []
    for row in parser.tables[0][1:]:
        if not row or row[0].lower().startswith("total"):
            continue
        padded = row + [""] * (len(header_row) - len(row))
        records.append({header_row[i]: padded[i] for i in range(len(header_row))})
    return records


def list_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return list(payload.get("data") or [])


def observed_list_fields(rows: list[dict[str, Any]]) -> list[str]:
    keys: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                keys.append(key)
    return keys


def field_presence(list_fields: list[str], history_fields: list[str]) -> dict[str, Any]:
    """Map requested conceptual fields to exact source names. Do not rename source columns."""
    list_set, history_set = set(list_fields), set(history_fields)
    mapping = {
        "road_name": {
            "present": "roadname" in list_set,
            "source_field_names": ["roadname"] if "roadname" in list_set else [],
            "where": "list JSON" if "roadname" in list_set else None,
        },
        "road_number": {
            "present": False,
            "source_field_names": [],
            "where": None,
        },
        "highway_number": {
            "present": False,
            "source_field_names": [],
            "where": None,
        },
        "road_segment": {
            "present": "ee_office_segment_id" in list_set or "segment_id" in list_set,
            "source_field_names": [name for name in ["ee_office_segment_id", "segment_id"] if name in list_set],
            "where": "list JSON",
        },
        "km_marker": {
            "present": "road_km_id" in list_set or "KM" in history_set,
            "source_field_names": [name for name in ["road_km_id", "KM"] if name in list_set or name in history_set],
            "where": "list JSON road_km_id; history table KM",
        },
        "district": {
            "present": "district_id" in list_set,
            "source_field_names": ["district_id"] if "district_id" in list_set else [],
            "where": "list JSON numeric id only; district name appeared in history page text, not as a column named district",
        },
        "latitude": {
            "present": "lat" in history_set,
            "source_field_names": ["lat"] if "lat" in history_set else [],
            "where": "segment history HTML table" if "lat" in history_set else None,
        },
        "longitude": {
            "present": "lng" in history_set,
            "source_field_names": ["lng"] if "lng" in history_set else [],
            "where": "segment history HTML table" if "lng" in history_set else None,
        },
        "event_date": {
            "present": "event_datetime" in list_set,
            "source_field_names": ["event_datetime"] if "event_datetime" in list_set else [],
            "where": "list JSON combined datetime; no separate event_date column",
        },
        "event_time": {
            "present": "event_datetime" in list_set,
            "source_field_names": ["event_datetime"] if "event_datetime" in list_set else [],
            "where": "list JSON combined datetime; no separate event_time column",
        },
        "closure_start": {
            "present": "Closed On" in history_set,
            "source_field_names": ["Closed On"] if "Closed On" in history_set else [],
            "where": "segment history HTML table" if "Closed On" in history_set else None,
        },
        "closure_end": {
            "present": "Opened On" in history_set,
            "source_field_names": ["Opened On"] if "Opened On" in history_set else [],
            "where": "segment history HTML table" if "Opened On" in history_set else None,
        },
        "closure_status": {
            "present": "status" in list_set or "Open Type" in history_set or "Status" in history_set,
            "source_field_names": [name for name in ["status", "Open Type", "Status"] if name in list_set or name in history_set],
            "where": "list JSON status; history Open Type and Status",
        },
        "reason": {
            "present": "Remark" in history_set,
            "source_field_names": ["Remark"] if "Remark" in history_set else [],
            "where": "segment history HTML table" if "Remark" in history_set else None,
        },
        "hazard_type": {
            "present": "Damage Type" in history_set,
            "source_field_names": ["Damage Type"] if "Damage Type" in history_set else [],
            "where": "segment history HTML table" if "Damage Type" in history_set else None,
        },
        "source_record_id": {
            "present": "ID" in history_set,
            "source_field_names": ["ID"] if "ID" in history_set else [],
            "where": "segment history HTML table ID; list JSON has DT_RowIndex (page index) and internal ids but not a field named source_record_id",
        },
    }
    return {field: mapping[field] for field in REQUESTED_FIELDS}


def unique_roads(rows: list[dict[str, Any]]) -> dict[str, Any]:
    names = [strip_html(row.get("roadname")) for row in rows]
    names = [name for name in names if name]
    road_ids = [row.get("road_id") for row in rows if row.get("road_id") is not None]
    return {
        "unique_roadname_count": len(set(names)),
        "unique_road_id_count": len(set(road_ids)),
        "unique_roadnames": sorted(set(names)),
        "unique_road_ids": sorted(set(road_ids)),
    }


def date_range_for(values: list[str]) -> dict[str, str | None]:
    cleaned = [value for value in values if value]
    if not cleaned:
        return {"min": None, "max": None}
    return {"min": min(cleaned), "max": max(cleaned)}


def status_semantics(observed: list[str]) -> list[dict[str, str]]:
    """Do not invent meanings. Documented widget labels are recorded separately from row values."""
    known_docs = {
        "Opened": "Dashboard widget label. No field dictionary was published. Semantics UNKNOWN beyond the label text.",
        "P Closed": "Dashboard widget label. No field dictionary was published. Semantics UNKNOWN; expansion not documented on the page.",
        "Closed": "Dashboard widget label. No field dictionary was published. Semantics UNKNOWN beyond the label text.",
        "Km already Opened": "Dashboard progress label. Semantics UNKNOWN beyond the label text.",
        "Km partially Opened": "Dashboard progress label. Semantics UNKNOWN beyond the label text.",
    }
    rows = []
    for value in observed:
        rows.append({
            "value": value,
            "semantics": known_docs.get(value, "UNKNOWN — no published status dictionary was found on the public page."),
        })
    return rows


def road_identity_feasibility(list_sample_rows: list[dict[str, Any]], history_rows: list[dict[str, str]]) -> dict[str, Any]:
    example_name = strip_html(list_sample_rows[0].get("roadname")) if list_sample_rows else None
    history_with_coords = [
        row for row in history_rows
        if not is_empty(row.get("lat")) and not is_empty(row.get("lng"))
    ]
    list_has_coords = any(key in (list_sample_rows[0] if list_sample_rows else {}) for key in ("lat", "lng", "latitude", "longitude"))
    unique_osm_without_guessing = bool(history_with_coords) and bool(example_name)
    return {
        "list_json_has_road_name": bool(example_name),
        "example_road_name": example_name,
        "list_json_has_highway_or_reference_number": False,
        "list_json_has_km_values": any(not is_empty(row.get("road_km_id")) for row in list_sample_rows),
        "list_json_has_coordinates": list_has_coords,
        "list_json_has_district_name": False,
        "list_json_has_district_id": any(row.get("district_id") is not None for row in list_sample_rows),
        "list_json_has_segment_id": any(row.get("ee_office_segment_id") not in (None, "") for row in list_sample_rows),
        "history_page_has_lat_lng": bool(history_with_coords),
        "history_coordinate_examples": [
            {"KM": row.get("KM"), "lat": row.get("lat"), "lng": row.get("lng"), "ID": row.get("ID")}
            for row in history_with_coords
        ],
        "can_map_to_unique_osm_road_without_guessing": unique_osm_without_guessing,
        "osm_mapping_answer": (
            "Yes for a unique location on the named highway, using the public segment-history page "
            "lat/lng plus KM, without inventing a road name. Unique OSM way ID was not computed in this phase."
            if unique_osm_without_guessing else
            "No. The list JSON names a road and KM/segment ids but has no coordinates or highway number field, so OSM matching would require guessing."
        ),
        "large_scale_osm_matching_run": False,
    }


def audit(list_payload: dict[str, Any], history_html: str) -> dict[str, Any]:
    rows = list_rows(list_payload)
    history_rows = parse_history_tables(history_html)
    list_fields = observed_list_fields(rows)
    history_fields = list(history_rows[0].keys()) if history_rows else []
    list_statuses = sorted({str(row.get("status")) for row in rows if row.get("status") not in (None, "")})
    history_open_types = sorted({row.get("Open Type") or "" for row in history_rows if row.get("Open Type")})
    history_damage = sorted({row.get("Damage Type") or "" for row in history_rows if row.get("Damage Type")})
    widget_labels = ["Opened", "P Closed", "Closed", "Km already Opened", "Km partially Opened"]
    presence = field_presence(list_fields, history_fields)
    return {
        "phase": "P3 Road Risk — Phase 9A",
        "scope": "Access and schema audit only. No Model B training, disruption_probability, satellite-label, hybrid-weight, dataset-build, or large OSM matching.",
        "sample": {
            "list_file": str(LIST_SAMPLE.relative_to(ROOT)) if LIST_SAMPLE.exists() else None,
            "history_file": str(HISTORY_SAMPLE.relative_to(ROOT)) if HISTORY_SAMPLE.exists() else None,
            "list_record_count": len(rows),
            "dashboard_records_total": list_payload.get("recordsTotal"),
            "dashboard_records_filtered": list_payload.get("recordsFiltered"),
            "history_event_count": len(history_rows),
            "list_date_range": date_range_for([str(row.get("event_datetime") or "") for row in rows]),
            "history_closed_on_range": date_range_for([row.get("Closed On") or "" for row in history_rows]),
        },
        "observed_list_fields": list_fields,
        "observed_history_fields": history_fields,
        "requested_field_presence": presence,
        "null_percentage_list": {field: null_pct(rows, field) for field in list_fields},
        "null_percentage_history": {field: null_pct(history_rows, field) for field in history_fields},
        "unique_roads": unique_roads(rows),
        "status_values": {
            "list_json_status": list_statuses,
            "history_open_type": history_open_types,
            "dashboard_widget_labels_observed_on_public_page": widget_labels,
            "history_damage_type": history_damage,
            "semantics": status_semantics(list_statuses + history_open_types + widget_labels),
        },
        "road_identity_feasibility": road_identity_feasibility(rows, history_rows),
        "important_missing_fields": [
            field for field, info in presence.items() if not info["present"]
        ],
    }


def markdown_for_schema(audit_doc: dict[str, Any]) -> str:
    presence = audit_doc["requested_field_presence"]
    lines = [
        "# Uttarakhand PWD schema audit",
        "",
        "**Phase:** P3 Road Risk — Phase 9A",
        "**Scope:** inspect the saved public sample only. Source column names are not renamed.",
        "",
        f"- List sample records: {audit_doc['sample']['list_record_count']}",
        f"- Dashboard-reported `recordsTotal`: {audit_doc['sample']['dashboard_records_total']}",
        f"- History-page events (segment 5731): {audit_doc['sample']['history_event_count']}",
        f"- List `event_datetime` range: {audit_doc['sample']['list_date_range']['min']} to {audit_doc['sample']['list_date_range']['max']}",
        "",
        "## Requested field presence",
        "",
        "| Requested field | Present | Exact source field names | Where |",
        "|---|---|---|---|",
    ]
    for field in REQUESTED_FIELDS:
        info = presence[field]
        names = ", ".join(info["source_field_names"]) if info["source_field_names"] else "—"
        where = info["where"] or "—"
        lines.append(f"| `{field}` | {'yes' if info['present'] else 'no'} | `{names}` | {where} |")
    lines += [
        "",
        "## List JSON fields and null percentage",
        "",
        "| Field | Null % |",
        "|---|---:|",
    ]
    for field, pct in audit_doc["null_percentage_list"].items():
        lines.append(f"| `{field}` | {pct} |")
    lines += [
        "",
        "## History table fields and null percentage",
        "",
        "| Field | Null % |",
        "|---|---:|",
    ]
    for field, pct in audit_doc["null_percentage_history"].items():
        lines.append(f"| `{field}` | {pct} |")
    roads = audit_doc["unique_roads"]
    lines += [
        "",
        "## Unique roads in the list sample",
        "",
        f"- Unique `roadname` values: {roads['unique_roadname_count']}",
        f"- Unique `road_id` values: {roads['unique_road_id_count']}",
        "",
        "## Status values",
        "",
        f"- List JSON `status`: {', '.join(audit_doc['status_values']['list_json_status']) or '—'}",
        f"- History `Open Type`: {', '.join(audit_doc['status_values']['history_open_type']) or '—'}",
        f"- Dashboard widgets: {', '.join(audit_doc['status_values']['dashboard_widget_labels_observed_on_public_page'])}",
        "",
        "Semantics are UNKNOWN where PWD did not publish a dictionary. Observed labels are not remapped.",
        "",
        "## Road identity",
        "",
        audit_doc["road_identity_feasibility"]["osm_mapping_answer"],
        "",
    ]
    return "\n".join(lines) + "\n"


def phase9a_report(audit_doc: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    presence = audit_doc["requested_field_presence"]
    identity_fields = [name for name in ["roadname", "ee_office_segment_id", "segment_id", "road_id", "road_km_id", "district_id"] if name in audit_doc["observed_list_fields"]]
    identity_fields += [name for name in ["KM", "lat", "lng", "ID"] if name in audit_doc["observed_history_fields"]]
    return {
        "report_title": "Phase 9A — Uttarakhand PWD source access and schema discovery",
        "phase": "P3 Road Risk — Phase 9A",
        "access_status": "C — public web interface with documented table export controls; list rows are also returned as JSON from the same public GET URL used by the dashboard. Login exists for other MIS functions and was not used. No bulk historical archive download was performed.",
        "access_status_code": "C",
        "data_acquired": True,
        "source_url_or_reference": SOURCE_URL,
        "additional_identified_urls": [SRMD_URL, SRMD_PAGE_URL, LOGIN_URL],
        "access_method": manifest["files"][0]["access_method"],
        "sample_size": {
            "list_json_rows": audit_doc["sample"]["list_record_count"],
            "dashboard_records_total_for_default_filters": audit_doc["sample"]["dashboard_records_total"],
            "segment_history_events": audit_doc["sample"]["history_event_count"],
        },
        "available_road_identity_fields": identity_fields,
        "timestamp_fields": ["event_datetime", "tc_date", "Closed On", "Tentative Date", "Opened On"],
        "closure_status_fields": ["status", "Open Type", "Status"],
        "reopening_information": {
            "present": True,
            "source_fields": ["Opened On", "Open Type", "Status"],
            "note": "History page shows Opened On and Open Type=Opened for the sampled segment. Dashboard widgets include Opened / Km already Opened. Meanings remain UNKNOWN without a PWD dictionary.",
        },
        "important_missing_fields": [
            "No dedicated highway_number or road_number column",
            "No district name column on the list JSON (numeric district_id only)",
            "No latitude/longitude on the list JSON (lat/lng appear on the linked segment-history page, and one history row lacked coordinates)",
            "No separate event_date or event_time columns",
            "No published status dictionary",
            "No explicit reuse licence",
        ],
        "suitable_for_next_phase": True,
        "suitable_for_next_phase_reason": "The public MIS supplies named roads, segment/KM identifiers, dated events, status text, and (on the history page) closure/opening timestamps plus coordinates. It is promising for a later small labeled dataset after status semantics and OSM matching are audited. It is not yet a training set.",
        "srmd_companion": {
            "url": SRMD_URL,
            "access": "Public HTML archive of daily morning/evening PDF reports. PDFs are directly downloadable from cdnbbsr.s3waas.gov.in. No login observed.",
            "sample_acquired_this_phase": False,
            "reason": "Structured MIS JSON was preferred over PDF extraction for schema discovery. A DMS 'Road Closure Report, List' link on the SRMD page redirected to a YouTube URL and was not treated as a dataset.",
        },
        "not_done": [
            "Model B training",
            "disruption_probability generation",
            "satellite label changes",
            "hybrid weight changes",
            "final road-disruption dataset build",
            "large OSM matching",
            "authentication bypass",
        ],
        "requested_field_presence": presence,
        "status_values": audit_doc["status_values"],
        "road_identity_feasibility": audit_doc["road_identity_feasibility"],
    }


def markdown_for_phase9a(report: dict[str, Any]) -> str:
    return "\n".join([
        "# Phase 9A — Uttarakhand PWD source access and schema discovery",
        "",
        "**Access status:** " + report["access_status"],
        "",
        f"- Data acquired: {'yes' if report['data_acquired'] else 'no'}",
        f"- Source URL: {report['source_url_or_reference']}",
        f"- Access method: {report['access_method']}",
        f"- Sample size: {report['sample_size']['list_json_rows']} list rows (dashboard reported {report['sample_size']['dashboard_records_total_for_default_filters']} filtered rows); {report['sample_size']['segment_history_events']} history events for one public segment page",
        f"- Road identity fields: {', '.join(f'`{name}`' for name in report['available_road_identity_fields'])}",
        f"- Timestamp fields: {', '.join(f'`{name}`' for name in report['timestamp_fields'])}",
        f"- Closure status fields: {', '.join(f'`{name}`' for name in report['closure_status_fields'])}",
        f"- Reopening information: {report['reopening_information']['note']}",
        "",
        "## Important missing fields",
        "",
        *[f"- {item}" for item in report["important_missing_fields"]],
        "",
        "## Suitability for the next phase",
        "",
        "Suitable: " + ("yes" if report["suitable_for_next_phase"] else "no") + ". " + report["suitable_for_next_phase_reason"],
        "",
        "This phase stops at access and schema audit.",
        "",
    ]) + "\n"


def write_manifest(retrieval_timestamp: str) -> dict[str, Any]:
    files = []
    for path, extra in [
        (LIST_SAMPLE, {
            "access_method": "Public GET of https://mis.pwduk.in/pwd/roadClosureStatus as used by the dashboard DataTables request (same URL as the public page; first page only, length=10). Table Options on the page loads DataTables HTML5 export scripts. Not a separately documented bulk API.",
            "date_range": None,
        }),
        (HISTORY_SAMPLE, {
            "access_method": "Public GET of the segment-history URL linked from the public list sample (eeOfficeSegmentHistory/5731). CSRF token redacted in the saved copy.",
            "date_range": None,
        }),
    ]:
        files.append({
            "source_name": SOURCE_NAME,
            "publisher": PUBLISHER,
            "source_url": SOURCE_URL if path == LIST_SAMPLE else "https://mis.pwduk.in/pwd/eeOfficeSegmentHistory/5731",
            "access_method": extra["access_method"],
            "retrieval_timestamp": retrieval_timestamp,
            "file_name": path.name,
            "sha256": sha256_file(path),
            "date_range": extra["date_range"],
            "geographic_scope": GEOGRAPHIC_SCOPE,
            "authentication_required": False,
            "license_or_reuse_information": "Government of Uttarakhand PWD website. No explicit reuse licence was found on the public pages reviewed.",
        })
    payload = json.loads(LIST_SAMPLE.read_text())
    rows = list_rows(payload)
    files[0]["date_range"] = date_range_for([str(row.get("event_datetime") or "") for row in rows])
    history_rows = parse_history_tables(HISTORY_SAMPLE.read_text(errors="replace"))
    files[1]["date_range"] = date_range_for([row.get("Closed On") or "" for row in history_rows])
    manifest = {
        "source_name": SOURCE_NAME,
        "publisher": PUBLISHER,
        "source_url": SOURCE_URL,
        "access_method": files[0]["access_method"],
        "retrieval_timestamp": retrieval_timestamp,
        "file_name": files[0]["file_name"],
        "sha256": files[0]["sha256"],
        "date_range": files[0]["date_range"],
        "geographic_scope": GEOGRAPHIC_SCOPE,
        "authentication_required": False,
        "license_or_reuse_information": files[0]["license_or_reuse_information"],
        "files": files,
        "companion_source": {
            "source_name": "Uttarakhand PWD SRMD Daily Reports",
            "source_url": SRMD_URL,
            "access_method": "Public document archive; PDFs linked from the category page.",
            "authentication_required": False,
            "sample_acquired": False,
        },
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def write_reports(retrieval_timestamp: str | None = None) -> dict[str, Any]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = retrieval_timestamp or now_utc()
    list_payload = json.loads(LIST_SAMPLE.read_text())
    history_html = HISTORY_SAMPLE.read_text(errors="replace")
    audit_doc = audit(list_payload, history_html)
    audit_doc["retrieval_timestamp"] = timestamp
    schema_json = REPORT_DIR / "uttarakhand_pwd_schema_audit.json"
    schema_md = REPORT_DIR / "uttarakhand_pwd_schema_audit.md"
    schema_json.write_text(json.dumps(audit_doc, indent=2) + "\n")
    schema_md.write_text(markdown_for_schema(audit_doc))
    manifest = write_manifest(timestamp)
    phase = phase9a_report(audit_doc, manifest)
    phase["retrieval_timestamp"] = timestamp
    (REPORT_DIR / "phase9a_pwd_access_report.json").write_text(json.dumps(phase, indent=2) + "\n")
    (REPORT_DIR / "phase9a_pwd_access_report.md").write_text(markdown_for_phase9a(phase))
    return {"audit": audit_doc, "phase9a": phase, "manifest": manifest}


if __name__ == "__main__":
    write_reports()
