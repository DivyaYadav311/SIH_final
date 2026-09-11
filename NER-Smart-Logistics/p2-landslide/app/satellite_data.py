"""Best-effort Sentinel-2 scene discovery for prediction provenance.

Satellite availability never becomes a requirement for a prediction: the live
weather and terrain pipeline remains available when image discovery fails.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import requests

PLANETARY_COMPUTER_STAC = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
TIMEOUT_SECONDS = 12


def latest_sentinel2_observation(latitude: float, longitude: float) -> dict[str, Any]:
    """Return metadata for the latest recent low-cloud Sentinel-2 L2A scene."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=180)
    payload = {
        "collections": ["sentinel-2-l2a"],
        "bbox": [longitude - 0.005, latitude - 0.005, longitude + 0.005, latitude + 0.005],
        "datetime": f"{start.strftime('%Y-%m-%dT%H:%M:%SZ')}/{end.strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "limit": 10,
        "query": {"eo:cloud_cover": {"lt": 30}},
        "sortby": [{"field": "datetime", "direction": "desc"}],
    }
    response = requests.post(PLANETARY_COMPUTER_STAC, json=payload, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    features = response.json().get("features", [])
    if not features:
        return {
            "status": "no_recent_cloud_acceptable_scene",
            "provider": "Microsoft Planetary Computer Sentinel-2 L2A STAC",
        }
    item = features[0]
    properties = item.get("properties", {})
    return {
        "status": "available",
        "provider": "Microsoft Planetary Computer Sentinel-2 L2A STAC",
        "scene_id": item.get("id"),
        "acquired_at": properties.get("datetime"),
        "cloud_cover_percent": properties.get("eo:cloud_cover"),
        "platform": properties.get("platform"),
        "collection": item.get("collection", "sentinel-2-l2a"),
    }


def collect_satellite_observation(latitude: float, longitude: float) -> dict[str, Any]:
    """Return explicit status rather than ever stopping the prediction."""
    try:
        return latest_sentinel2_observation(latitude, longitude)
    except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
        return {
            "status": "unavailable",
            "provider": "Microsoft Planetary Computer Sentinel-2 L2A STAC",
            "message": str(exc),
        }
