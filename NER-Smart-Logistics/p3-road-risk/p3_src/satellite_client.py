"""Small, cached client for Copernicus Data Space catalog and Process APIs."""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
CATALOG_URL = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
PROCESS_URL = "https://sh.dataspace.copernicus.eu/api/v1/process"
P3_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DOTENV_PATH = P3_ROOT / ".env"
CDSE_KEYS = ("CDSE_CLIENT_ID", "CDSE_CLIENT_SECRET")


def event_windows(event_date: str, event_days: int = 1) -> dict[str, tuple[str, str]]:
    """Return inclusive UTC date windows; post-event windows are verification-only."""
    date = datetime.fromisoformat(event_date).date()
    ranges = {
        "before_30_15": (date - timedelta(days=30), date - timedelta(days=15)),
        "before_14_7": (date - timedelta(days=14), date - timedelta(days=7)),
        "before_6_1": (date - timedelta(days=6), date - timedelta(days=1)),
        "event": (date - timedelta(days=event_days), date + timedelta(days=event_days)),
        "after_1_6": (date + timedelta(days=1), date + timedelta(days=6)),
        "after_7_14": (date + timedelta(days=7), date + timedelta(days=14)),
        "after_15_30": (date + timedelta(days=15), date + timedelta(days=30)),
    }
    return {name: (start.isoformat(), end.isoformat()) for name, (start, end) in ranges.items()}


def buffer_bbox(latitude: float, longitude: float, buffer_m: float = 250.0) -> tuple[float, float, float, float]:
    """Approximate a metric circle with a WGS84 bbox for small event buffers."""
    import math

    lat_delta = buffer_m / 111_320.0
    lon_delta = buffer_m / (111_320.0 * max(math.cos(math.radians(latitude)), 1e-6))
    return (longitude - lon_delta, latitude - lat_delta, longitude + lon_delta, latitude + lat_delta)


def bbox_geojson(bbox: tuple[float, float, float, float]) -> dict[str, Any]:
    west, south, east, north = bbox
    return {
        "type": "Polygon",
        "coordinates": [[[west, south], [east, south], [east, north], [west, north], [west, south]]],
    }


def process_payload(satellite: str, bbox: tuple[float, float, float, float], start: str, end: str,
                   product_id: str | None = None) -> dict[str, Any]:
    """Build a small-area Process API request for the bands used by the experiment."""
    collections = {
        "sentinel-1": ("sentinel-1-grd", ["VV", "VH"], "return [sample.VV, sample.VH];"),
        "sentinel-2": ("sentinel-2-l2a", ["B02", "B03", "B04", "B08", "B11", "B12", "SCL"],
                   "return [sample.B02, sample.B03, sample.B04, sample.B08, sample.B11, sample.B12, sample.SCL];"),
    }
    collection, bands, body = collections[satellite]
    data_filter = {"timeRange": {"from": f"{start}T00:00:00Z", "to": f"{end}T23:59:59Z"}}
    if product_id:
        data_filter["id"] = product_id
    return {
        "input": {"bounds": {"bbox": list(bbox)}, "data": [{"type": collection, "dataFilter": data_filter}]},
        "output": {"width": 32, "height": 32, "responses": [{"identifier": "default", "format": {"type": "image/tiff"}}]},
        "evalscript": f"//VERSION=3\nfunction setup() {{ return {{input: {json.dumps(bands)}, output: {{bands: {len(bands)}, sampleType: 'FLOAT32'}}}}; }}\nfunction evaluatePixel(sample) {{ {body} }}",
    }


def load_cdse_credentials(dotenv_path: str | Path | None = None) -> dict[str, str]:
    """Load P3 credentials without allowing dotenv values to override exports."""
    path = Path(dotenv_path) if dotenv_path else DEFAULT_DOTENV_PATH
    load_dotenv(dotenv_path=path, override=False)
    return {key: os.getenv(key, "") for key in CDSE_KEYS}


def credential_status(dotenv_path: str | Path | None = None) -> dict[str, str]:
    """Return only configured/missing status; never return credential contents."""
    values = load_cdse_credentials(dotenv_path)
    return {key: "configured" if values[key] else "missing" for key in CDSE_KEYS}


class CDSEClient:
    def __init__(self, cache_dir: str | Path, timeout: float = 60.0, min_request_interval: float = 0.2,
                 session: requests.Session | None = None) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.min_request_interval = min_request_interval
        self.session = session or requests.Session()
        self._last_request = 0.0
        self._token: str | None = None

    @staticmethod
    def credentials_available() -> bool:
        values = load_cdse_credentials()
        return bool(values["CDSE_CLIENT_ID"] and values["CDSE_CLIENT_SECRET"])

    def _throttle(self) -> None:
        delay = self.min_request_interval - (time.monotonic() - self._last_request)
        if delay > 0:
            time.sleep(delay)
        self._last_request = time.monotonic()

    def _request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        kwargs.setdefault("timeout", self.timeout)
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                self._throttle()
                response = self.session.request(method, url, **kwargs)
                if response.status_code in {429, 500, 502, 503, 504} and attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                response.raise_for_status()
                return response
            except (requests.RequestException, ValueError) as error:
                last_error = error
                if attempt < 2:
                    time.sleep(2 ** attempt)
        raise RuntimeError(f"CDSE request failed after retries: {url}") from last_error

    def authenticate(self) -> str:
        credentials = load_cdse_credentials()
        client_id = credentials["CDSE_CLIENT_ID"]
        client_secret = credentials["CDSE_CLIENT_SECRET"]
        if not client_id or not client_secret:
            raise RuntimeError("CDSE_CLIENT_ID and CDSE_CLIENT_SECRET are required for satellite acquisition")
        response = self._request("POST", TOKEN_URL, data={
            "grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret,
        })
        self._token = response.json()["access_token"]
        return self._token

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token or self.authenticate()}"}

    def _cached_json(self, key: dict[str, Any], producer) -> dict[str, Any]:
        digest = hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest()
        path = self.cache_dir / f"{digest}.json"
        if path.exists():
            return json.loads(path.read_text())
        payload = producer()
        path.write_text(json.dumps(payload, indent=2, default=str))
        return payload

    def search_catalog(self, collection: str, bbox: tuple[float, float, float, float], start: str, end: str,
                       cloud_cover_max: float | None = None) -> list[dict[str, Any]]:
        west, south, east, north = bbox
        filters = [
            f"Collection/Name eq '{collection}'",
            f"ContentDate/Start ge {start}T00:00:00.000Z",
            f"ContentDate/Start le {end}T23:59:59.999Z",
            f"OData.CSC.Intersects(area=geography'SRID=4326;POLYGON(({west} {south},{east} {south},{east} {north},{west} {north},{west} {south}))')",
        ]
        if cloud_cover_max is not None:
            filters.append(f"Attributes/OData.CSC.DoubleAttribute/any(a:a/Name eq 'cloudCover' and a/Value le {float(cloud_cover_max)})")
        params = {"$filter": " and ".join(filters), "$top": 1000}
        key = {"endpoint": CATALOG_URL, "params": params}
        payload = self._cached_json(key, lambda: self._request("GET", CATALOG_URL, params=params).json())
        return payload.get("value", [])

    def process(self, payload: dict[str, Any]) -> bytes:
        response = self._request("POST", PROCESS_URL, headers={**self._auth_headers(), "Content-Type": "application/json"}, json=payload)
        return response.content

    def process_cached(self, payload: dict[str, Any]) -> tuple[bytes, bool, str]:
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        path = self.cache_dir / f"{digest}.bin"
        if path.exists():
            return path.read_bytes(), True, digest
        content = self.process(payload)
        path.write_bytes(content)
        return content, False, digest


if __name__ == "__main__":
    print(json.dumps(credential_status()))