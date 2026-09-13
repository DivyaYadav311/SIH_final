"""Optional HTTP clients for P4 routing and P5 logistics."""
from __future__ import annotations

import logging
from typing import Any

import httpx

from p6_src.config import p4_base_url, p5_base_url

log = logging.getLogger(__name__)


def fetch_p5_shipments() -> list[dict[str, Any]] | None:
    base = p5_base_url()
    if not base:
        return None
    try:
        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            r = client.get(f"{base}/api/v1/shipments")
            r.raise_for_status()
            payload = r.json()
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for key in ("shipments", "items", "data"):
                if isinstance(payload.get(key), list):
                    return payload[key]
        return None
    except Exception as exc:
        log.warning("P5 shipments unavailable: %s", exc)
        return None


def _origin_destination_payload(origin: Any, destination: Any) -> dict[str, Any]:
    body: dict[str, Any] = {}
    if isinstance(origin, dict):
        body["origin"] = origin
    elif origin not in (None, ""):
        body["origin"] = str(origin)
    if isinstance(destination, dict):
        body["destination"] = destination
    elif destination not in (None, ""):
        body["destination"] = str(destination)
    return body


def request_p4_route(
    origin: Any,
    destination: Any,
    *,
    cargo_type: str | None = None,
    priority: str | None = None,
    avoid_high_risk_roads: bool | None = None,
) -> dict[str, Any] | None:
    """Return the full P4 optimize payload, or None if routing is unavailable."""
    base = p4_base_url()
    if not base:
        return None
    body = _origin_destination_payload(origin, destination)
    if not body.get("origin") or not body.get("destination"):
        return None
    if cargo_type:
        body["cargo_type"] = str(cargo_type).lower()
    if priority:
        body["priority"] = str(priority).lower()
    if avoid_high_risk_roads is not None:
        body["constraints"] = {"avoid_high_risk_roads": bool(avoid_high_risk_roads)}
    try:
        with httpx.Client(timeout=60.0, follow_redirects=True) as client:
            r = client.post(f"{base}/api/v1/routes/optimize", json=body)
            r.raise_for_status()
            payload = r.json()
        return payload if isinstance(payload, dict) else None
    except Exception as exc:
        log.warning("P4 optimize unavailable: %s", exc)
        return None


def request_p4_alternative(origin: Any, destination: Any) -> str | None:
    payload = request_p4_route(origin, destination, avoid_high_risk_roads=True)
    if not payload:
        return None
    route_id = payload.get("route_id")
    return str(route_id) if route_id else None
