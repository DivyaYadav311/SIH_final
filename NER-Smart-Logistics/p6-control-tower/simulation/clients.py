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


def request_p4_alternative(
    origin: str | dict[str, float],
    destination: str | dict[str, float],
    cargo_type: str | None = None,
    priority: str | None = None,
    transport_mode: str | None = None,
) -> dict[str, Any] | None:
    base = p4_base_url()
    if not base:
        return None
    try:
        payload: dict[str, Any] = {
            "origin": origin,
            "destination": destination,
            "constraints": {"avoid_high_risk_roads": True},
        }
        if cargo_type:
            payload["cargo_type"] = cargo_type
        if priority:
            payload["priority"] = priority
        if transport_mode:
            payload["transport_mode"] = transport_mode

        with httpx.Client(timeout=20.0, follow_redirects=True) as client:
            r = client.post(
                f"{base}/api/v1/routes/optimize",
                json=payload,
            )
            r.raise_for_status()
            payload = r.json()
        return payload if isinstance(payload, dict) else None
    except Exception as exc:
        log.warning("P4 optimize unavailable: %s", exc)
        return None
