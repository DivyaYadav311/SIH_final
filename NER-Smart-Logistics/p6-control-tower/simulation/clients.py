"""Optional HTTP clients for P4 routing and P5 logistics. Fail closed to snapshots."""
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


def request_p4_alternative(origin: dict[str, float], destination: dict[str, float]) -> str | None:
    base = p4_base_url()
    if not base:
        return None
    try:
        with httpx.Client(timeout=20.0, follow_redirects=True) as client:
            r = client.post(
                f"{base}/api/v1/routes/optimize",
                json={
                    "origin": origin,
                    "destination": destination,
                    "cargo_type": "MEDICINE",
                    "priority": "CRITICAL",
                    "constraints": {"avoid_high_risk_roads": True},
                },
            )
            r.raise_for_status()
            payload = r.json()
        route_id = payload.get("route_id")
        return str(route_id) if route_id else None
    except Exception as exc:
        log.warning("P4 optimize unavailable: %s", exc)
        return None
