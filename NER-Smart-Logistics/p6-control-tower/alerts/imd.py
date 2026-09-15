"""Official IMD CAP warnings from the WIS2 public API (independent of P4)."""
from __future__ import annotations

import base64
import logging
import xml.etree.ElementTree as ET
from typing import Any

import httpx

from p6_src.config import IMD_CAP_MESSAGES_URL, IMD_CAP_META

log = logging.getLogger(__name__)


def _cap_xml_from_item(item: dict) -> str | None:
    content = item.get("content") or {}
    if isinstance(content, dict) and content.get("encoding") == "base64":
        try:
            return base64.b64decode(content.get("value", "")).decode("utf-8", "ignore")
        except Exception:
            return None
    return None


def _tag(root: ET.Element, name: str) -> str:
    for el in root.iter():
        if el.tag.split("}")[-1] == name:
            return (el.text or "").strip()
    return ""


def _cap_severity_to_level(raw: str) -> str:
    s = (raw or "").lower()
    if s in ("extreme", "severe"):
        return "CRITICAL" if s == "extreme" else "HIGH"
    if s == "moderate":
        return "MEDIUM"
    return "LOW"


def fetch_imd_cap_alerts(limit: int = 100) -> list[dict[str, Any]]:
    try:
        with httpx.Client(timeout=15, verify=False, follow_redirects=True) as client:
            r = client.get(IMD_CAP_MESSAGES_URL, params={"limit": limit, "f": "json"})
            r.raise_for_status()
            payload = r.json()
    except Exception as exc:
        log.warning("IMD CAP feed unavailable: %s", exc)
        return []

    items = payload.get("features", payload.get("items", [])) if isinstance(payload, dict) else []
    alerts: list[dict[str, Any]] = []
    for item in items:
        props = item.get("properties", item) if isinstance(item, dict) else {}
        if props.get("metadata_id") != IMD_CAP_META and not str(props.get("data_id", "")).startswith(
            "in-imd:cap_alerts"
        ):
            continue
        xml = _cap_xml_from_item(props)
        if not xml:
            continue
        try:
            root = ET.fromstring(xml)
        except ET.ParseError:
            continue
        severity = _tag(root, "severity")
        alerts.append(
            {
                "identifier": _tag(root, "identifier"),
                "event": _tag(root, "event"),
                "severity": severity,
                "risk_level": _cap_severity_to_level(severity),
                "area": _tag(root, "areaDesc"),
                "headline": _tag(root, "headline"),
                "description": _tag(root, "description"),
                "instruction": _tag(root, "instruction"),
                "sent": _tag(root, "sent"),
                "expires": _tag(root, "expires"),
                "polygon": _tag(root, "polygon"),
                "source": "IMD_CAP",
            }
        )
    return alerts
