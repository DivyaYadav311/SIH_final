from __future__ import annotations

import csv
import hashlib
import re
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Iterable, List
from urllib.parse import urljoin
import xml.etree.ElementTree as ET

import pandas as pd
import requests


ASDMA_BASE = "https://asdma.assam.gov.in"
REPORT_DISCOVERY_PAGES = [
    ASDMA_BASE + "/",
    ASDMA_BASE + "/documents/reports-3",
    ASDMA_BASE + "/resource/assam-flood-report",
    ASDMA_BASE + "/information-services/assam-flood-report-0",
    ASDMA_BASE + "/rss.xml",
]
REPORT_KEYWORDS = [
    "flood",
    "storm",
    "earthquake",
    "landslide",
    "report",
    "daily",
    "situation",
    "road",
    "bridge",
    "communication",
    "damage",
]

EVIDENCE_COLUMNS = [
    "incident_id",
    "source",
    "source_url",
    "source_file",
    "report_title",
    "report_date",
    "event_date",
    "state",
    "district",
    "location_text",
    "road_name",
    "road_reference",
    "incident_type",
    "impact_type",
    "original_text",
    "extraction_method",
    "evidence_confidence",
]

LABEL_COLUMNS = [
    "incident_id",
    "osm_road_id",
    "event_date",
    "road_disrupted",
    "label_confidence",
    "source",
    "source_url",
    "source_file",
    "source_page",
    "original_text",
]

REVIEW_COLUMNS = [
    "incident_id",
    "source",
    "source_url",
    "review_status",
    "reviewed_road_id",
    "reviewer_decision",
    "review_notes",
]

MANIFEST_COLUMNS = [
    "source_file",
    "source_url",
    "download_date",
    "report_date",
    "title",
    "sha256",
    "file_size_bytes",
]


def _strip_tags(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value, flags=re.DOTALL)
    value = unescape(value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_empty_csv(path: Path, columns: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(columns=list(columns)).to_csv(path, index=False)


def _discover_asdma_pages() -> List[dict]:
    discovered: List[dict] = []
    seen = set()

    for page_url in REPORT_DISCOVERY_PAGES:
        try:
            response = requests.get(page_url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
        except Exception:
            continue

        text = response.text
        for match in re.finditer(r'<a[^>]+href=["\']?(?P<href>[^"\'\s>]+)["\']?[^>]*>(?P<title>.*?)</a>', text, flags=re.IGNORECASE | re.DOTALL):
            href = match.group("href").strip()
            title = _strip_tags(match.group("title"))
            if not href:
                continue
            if href.startswith("mailto:"):
                continue
            absolute = href if href.startswith("http") else urljoin(page_url, href)
            combined_text = (title + " " + absolute).lower()
            if not any(keyword in combined_text for keyword in REPORT_KEYWORDS):
                continue
            if absolute in seen:
                continue
            seen.add(absolute)
            discovered.append({"source_url": absolute, "title": title or absolute})

    if not discovered:
        try:
            rss = requests.get(ASDMA_BASE + "/rss.xml", timeout=20, headers={"User-Agent": "Mozilla/5.0"})
            rss.raise_for_status()
            root = ET.fromstring(rss.text)
            for item in root.findall(".//item"):
                link = item.findtext("link")
                title = item.findtext("title")
                if not link:
                    continue
                if link in seen:
                    continue
                seen.add(link)
                discovered.append({"source_url": link, "title": title or link})
        except Exception:
            pass

    return discovered


def _discover_available_reports(project_root: Path) -> List[dict]:
    discovered = _discover_asdma_pages()
    raw_dir = project_root / "data" / "raw" / "incidents" / "asdma"
    raw_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = raw_dir / "manifest.csv"
    if discovered:
        rows = []
        for item in discovered:
            rows.append({
                "source_file": "",
                "source_url": item["source_url"],
                "download_date": "",
                "report_date": "",
                "title": item["title"],
                "sha256": "",
                "file_size_bytes": "",
            })
        pd.DataFrame(rows, columns=MANIFEST_COLUMNS).to_csv(manifest_path, index=False)
    else:
        _write_empty_csv(manifest_path, MANIFEST_COLUMNS)
    return discovered


def _download_reports(raw_dir: Path, discovered: List[dict]) -> List[dict]:
    downloaded: List[dict] = []
    if not discovered:
        return downloaded

    for item in discovered:
        source_url = item["source_url"]
        source_file = raw_dir / (source_url.rstrip("/").split("/")[-1] or "asdma_report.pdf")
        try:
            response = requests.get(source_url, timeout=25, headers={"User-Agent": "Mozilla/5.0"}, stream=True)
            response.raise_for_status()
        except Exception:
            continue

        if "application/pdf" not in response.headers.get("content-type", "").lower():
            continue

        with source_file.open("wb") as fh:
            for chunk in response.iter_content(chunk_size=65536):
                if chunk:
                    fh.write(chunk)

        downloaded.append({
            "source_file": source_file.name,
            "source_url": source_url,
            "download_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "report_date": "",
            "title": item["title"],
            "sha256": _hash_file(source_file),
            "file_size_bytes": source_file.stat().st_size,
        })

    if downloaded:
        pd.DataFrame(downloaded, columns=MANIFEST_COLUMNS).to_csv(raw_dir / "manifest.csv", index=False)
    return downloaded


def build_incident_dataset(project_root: str | Path = ".") -> dict:
    root = Path(project_root)
    raw_dir = root / "data" / "raw" / "incidents" / "asdma"
    processed_dir = root / "data" / "processed"
    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "reports_discovered": 0,
        "reports_downloaded": 0,
        "extraction_success_failure": "0/0",
        "ocr_count": 0,
        "road_impact_candidates": 0,
        "high_confidence_records": 0,
        "medium_confidence_records": 0,
        "low_confidence_records": 0,
        "records_with_coordinates": 0,
        "records_successfully_geocoded": 0,
        "osm_road_matches": 0,
        "ambiguous_matches": 0,
        "unmatched_records": 0,
        "date_coverage": "",
        "district_coverage": "",
        "real_road_impact_labels_available": False,
    }

    discovered = _discover_available_reports(root)
    summary["reports_discovered"] = len(discovered)

    downloaded = _download_reports(raw_dir, discovered)
    summary["reports_downloaded"] = len(downloaded)

    evidence_path = processed_dir / "road_impact_evidence.csv"
    labels_path = processed_dir / "road_impact_labels.csv"
    review_path = processed_dir / "road_impact_review.csv"

    _write_empty_csv(evidence_path, EVIDENCE_COLUMNS)
    _write_empty_csv(labels_path, LABEL_COLUMNS)
    _write_empty_csv(review_path, REVIEW_COLUMNS)

    summary["extraction_success_failure"] = f"{0}/{max(len(downloaded), 1)}"
    summary["date_coverage"] = "none"
    summary["district_coverage"] = "none"

    return summary


def main() -> None:
    summary = build_incident_dataset()
    print("STATUS: BLOCKED — REAL ROAD-IMPACT LABELS REQUIRED")
    print("reports_discovered=", summary["reports_discovered"])
    print("reports_downloaded=", summary["reports_downloaded"])
    print("road_impact_candidates=", summary["road_impact_candidates"])
    print("high_confidence_records=", summary["high_confidence_records"])
    print("medium_confidence_records=", summary["medium_confidence_records"])
    print("low_confidence_records=", summary["low_confidence_records"])
    print("records_with_coordinates=", summary["records_with_coordinates"])
    print("osm_road_matches=", summary["osm_road_matches"])
    print("ambiguous_matches=", summary["ambiguous_matches"])
    print("unmatched_records=", summary["unmatched_records"])
    print("date_coverage=", summary["date_coverage"])
    print("district_coverage=", summary["district_coverage"])
    print("output_paths=")
    print("  data/raw/incidents/asdma/manifest.csv")
    print("  data/processed/road_impact_evidence.csv")
    print("  data/processed/road_impact_labels.csv")
    print("  data/processed/road_impact_review.csv")


if __name__ == "__main__":
    main()
