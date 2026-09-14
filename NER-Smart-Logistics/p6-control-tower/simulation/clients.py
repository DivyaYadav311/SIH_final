"""Optional HTTP clients for P4 routing and P5 logistics."""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

import httpx

_P6_ROOT = Path(__file__).resolve().parents[1]
if str(_P6_ROOT) not in sys.path:
    sys.path.insert(0, str(_P6_ROOT))

try:
    from p6_src.config import p4_base_url, p5_base_url
except Exception:
    def p4_base_url() -> str:
        return (os.getenv("P4_BASE_URL") or "http://127.0.0.1:8002").rstrip("/")

    def p5_base_url() -> str:
        return (os.getenv("P5_BASE_URL") or "http://127.0.0.1:8002").rstrip("/")

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
        log.warning("P5 shipments via HTTP unavailable (%s), trying local in-process service...", exc)
        try:
            import importlib
            p5_main = importlib.import_module("p5_src.main")
            p5_service = getattr(p5_main, "service", None)
            if p5_service and hasattr(p5_service, "shipments"):
                return [s.model_dump() for s in p5_service.shipments.values()]
        except Exception:
            return None
        return None


def fetch_p4_route(
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
            "constraints": {"avoid_high_risk_roads": False},
        }
        if cargo_type:
            payload["cargo_type"] = cargo_type
        if priority:
            payload["priority"] = priority
        if transport_mode:
            payload["transport_mode"] = transport_mode

        with httpx.Client(timeout=60.0, follow_redirects=True) as client:
            r = client.post(
                f"{base}/api/v1/routes/optimize",
                json=payload,
            )
            r.raise_for_status()
            payload = r.json()
        return payload if isinstance(payload, dict) else None
    except Exception as exc:
        log.warning("P4 route fetch unavailable: %s", exc)
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

        with httpx.Client(timeout=60.0, follow_redirects=True) as client:
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

