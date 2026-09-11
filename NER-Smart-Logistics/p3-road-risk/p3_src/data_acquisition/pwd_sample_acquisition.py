"""Phase 9B: Acquire a controlled sample from PWD MIS via legitimate public access."""
from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw" / "training" / "uttarakhand_pwd"
RAW_DIR.mkdir(parents=True, exist_ok=True)

SOURCE_NAME = "Uttarakhand PWD Road Closure Status MIS"
PUBLISHER = "Public Works Department, Government of Uttarakhand"
SOURCE_URL = "https://mis.pwduk.in/pwd/roadClosureStatus"


def sha256_file(path: Path) -> str:
    """Compute SHA256 hash of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_string(content: str) -> str:
    """Compute SHA256 hash of a string."""
    return hashlib.sha256(content.encode()).hexdigest()


def now_utc() -> str:
    """Return current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def extract_segment_id(ee_office_segment_id_html: str) -> str | None:
    """Extract segment ID from HTML link."""
    match = re.search(r"eeOfficeSegmentHistory/(\d+)", str(ee_office_segment_id_html))
    return match.group(1) if match else None


def attempt_mis_access(
    params: dict[str, Any] | None = None,
    max_retries: int = 3,
    timeout: int = 15,
) -> dict[str, Any] | None:
    """
    Attempt to access the PWD MIS public endpoint with optional filtering.

    Does NOT bypass authentication. Uses only documented public access.

    Args:
        params: Query parameters (draw, start, length, search, etc.)
        max_retries: Number of retries on network error
        timeout: Timeout in seconds

    Returns:
        JSON response from MIS or None on failure
    """
    if params is None:
        params = {"draw": 1, "start": 0, "length": 100}

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": SOURCE_URL,
    })

    for attempt in range(max_retries):
        try:
            response = session.get(SOURCE_URL, params=params, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                wait = 2 ** attempt
                print(f"Attempt {attempt + 1} failed: {e}. Retrying in {wait}s...")
                time.sleep(wait)
            else:
                print(f"Failed after {max_retries} attempts: {e}")
                return None
    return None


def save_acquisition(
    response_data: dict[str, Any],
    filename_base: str,
    access_params: dict[str, Any],
) -> dict[str, Any]:
    """
    Save acquired JSON response with provenance.

    Args:
        response_data: JSON response from MIS
        filename_base: Base name for saved file
        access_params: Parameters used to fetch this data

    Returns:
        Provenance entry for the manifest
    """
    json_path = RAW_DIR / f"{filename_base}.json"
    json_path.write_text(json.dumps(response_data, indent=2))
    json_hash = sha256_file(json_path)

    record_count = len(response_data.get("data", []))
    total_records = response_data.get("recordsTotal", 0)

    provenance = {
        "source_name": SOURCE_NAME,
        "publisher": PUBLISHER,
        "source_url": SOURCE_URL,
        "access_method": f"Public GET with DataTables parameters: {access_params}",
        "retrieval_timestamp": now_utc(),
        "file_name": json_path.name,
        "sha256": json_hash,
        "record_count": record_count,
        "total_records_filtered": total_records,
        "access_parameters": access_params,
    }
    return provenance


def acquire_controlled_sample() -> dict[str, Any]:
    """
    Acquire a controlled sample from PWD MIS.

    Strategy:
    1. Fetch first page (length=100)
    2. If records available, continue with pagination until reaching limit

    Does NOT:
    - bypass authentication
    - scrape protected endpoints
    - infer missing data

    Returns:
        Summary of acquisition with provenance and file locations
    """
    print("=" * 80)
    print("PWD MIS CONTROLLED SAMPLE ACQUISITION")
    print("=" * 80)

    MAX_RECORDS = 500
    PAGE_SIZE = 100
    acquisitions = []

    # Attempt 1: Fetch first page
    print(f"\n[1] Attempting to fetch first {PAGE_SIZE} records...")
    params = {"draw": 1, "start": 0, "length": PAGE_SIZE}
    first_response = attempt_mis_access(params)

    if first_response is None:
        print("STOP: Cannot access PWD MIS public endpoint.")
        return {
            "success": False,
            "reason": "No public access available",
            "acquisitions": [],
        }

    prov1 = save_acquisition(first_response, "pwd_sample_page1", params)
    acquisitions.append(prov1)
    print(f"    ✓ Acquired {prov1['record_count']} records (total in MIS filter: {prov1['total_records_filtered']})")

    total_available = first_response.get("recordsTotal", 0)

    # Attempt 2: Pagination (if there are more records)
    if total_available > PAGE_SIZE:
        page_num = 2
        current_records = prov1["record_count"]

        while current_records < MAX_RECORDS and current_records < total_available:
            start = page_num - 1
            params = {"draw": page_num, "start": start * PAGE_SIZE, "length": PAGE_SIZE}
            print(f"\n[{page_num}] Fetching records {params['start']}-{params['start'] + PAGE_SIZE}...")

            page_response = attempt_mis_access(params)
            if page_response is None or not page_response.get("data"):
                print(f"    No more records available or error occurred.")
                break

            page_records = len(page_response.get("data", []))
            if page_records == 0:
                print("    Reached end of records.")
                break

            prov = save_acquisition(page_response, f"pwd_sample_page{page_num}", params)
            acquisitions.append(prov)
            print(f"    ✓ Acquired {prov['record_count']} records")

            current_records += page_records
            page_num += 1
            time.sleep(1)  # Respectful delay

    # Update manifest
    manifest = {
        "phase": "9B",
        "purpose": "Acquire controlled sample for PWD historical road-status dataset feasibility",
        "acquisition_timestamp": now_utc(),
        "total_acquisitions": len(acquisitions),
        "strategy": "Public GET with DataTables pagination",
        "max_target_records": MAX_RECORDS,
        "acquisitions": acquisitions,
    }

    manifest_path = RAW_DIR / "phase9b_acquisition_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))

    total_acquired = sum(a["record_count"] for a in acquisitions)

    print("\n" + "=" * 80)
    print("ACQUISITION COMPLETE")
    print("=" * 80)
    print(f"Total records acquired: {total_acquired}")
    print(f"Total in MIS filter: {total_available}")
    print(f"Files saved: {len(acquisitions)}")
    print(f"Manifest: {manifest_path}")

    return {
        "success": True,
        "total_acquired": total_acquired,
        "total_available": total_available,
        "acquisitions": acquisitions,
        "manifest": manifest_path,
    }


if __name__ == "__main__":
    result = acquire_controlled_sample()
    print(json.dumps({k: v for k, v in result.items() if k != "manifest"}, indent=2))
