"""Official/near-official India hazard and transit data adapters.

These adapters are intentionally fail-safe: a missing upstream feed never
creates a fake route.  Instead the API reports which data sources were used.
"""
from __future__ import annotations
import base64, logging, os, re, json, xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from typing import Any
import httpx

log = logging.getLogger(__name__)
IMD_CAP_MESSAGES = os.getenv("IMD_CAP_MESSAGES_URL", "https://wis2box.imd.gov.in/oapi/collections/messages/items")
IMD_CAP_META = "urn:wmo:md:in-imd:cap_alerts"
IMD_SACHET_POLYGON_URL_PARAM = "Polygon URL"
NRSC_WMS_URL = os.getenv("NRSC_BHUVAN_WMS_URL", "https://bhuvan-vec2.nrsc.gov.in/bhuvan/wms")
NRSC_LANDSLIDE_LAYER = os.getenv("NRSC_LANDSLIDE_LAYER", "disaster:RUOKKE_LHZ_01")
NRSC_LANDSLIDE_GEOJSON = os.getenv("NRSC_LANDSLIDE_GEOJSON", "")


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


def fetch_imd_cap_alerts(limit: int = 100) -> list[dict[str, Any]]:
    """Read recent public IMD CAP warnings from the WIS2 API."""
    try:
        with httpx.Client(timeout=2.0, verify=False, follow_redirects=True) as client:
            r = client.get(IMD_CAP_MESSAGES, params={"limit": limit, "f": "json"})
            r.raise_for_status()
            payload = r.json()
        items = payload.get("features", payload.get("items", [])) if isinstance(payload, dict) else []
        alerts = []
        for item in items:
            props = item.get("properties", item) if isinstance(item, dict) else {}
            if props.get("metadata_id") != IMD_CAP_META and not str(props.get("data_id", "")).startswith("in-imd:cap_alerts"):
                continue
            xml = _cap_xml_from_item(props)
            if not xml:
                continue
            try:
                root = ET.fromstring(xml)
                severity = _tag(root, "severity").lower()
                event = _tag(root, "event")
                area = _tag(root, "areaDesc")
                headline = _tag(root, "headline")
                expires = _tag(root, "expires")
                polygon = _tag(root, "polygon")
                # CAP records may publish the spatial polygon through a SACHET
                # parameter URL instead of embedding it in <polygon>.
                polygon_url = ""
                for el in root.iter():
                    if el.tag.split("}")[-1] == "parameter":
                        vals=[(x.text or "").strip() for x in list(el)]
                        if len(vals)>=2 and vals[0].lower()==IMD_SACHET_POLYGON_URL_PARAM.lower(): polygon_url=vals[1]
                alerts.append({"event": event, "severity": severity, "area": area, "headline": headline, "expires": expires, "polygon": polygon, "polygon_url": polygon_url})
            except ET.ParseError:
                continue
        return alerts
    except Exception as exc:
        log.warning("IMD CAP feed unavailable: %s", exc)
        return []


def imd_warning_risk_for_point(lat: float, lon: float, alerts: list[dict[str, Any]]) -> tuple[float, dict | None]:
    """Use CAP polygons when supplied. Falls back to no spatial claim.

    CAP alerts often publish a polygon. Point-in-polygon is implemented here
    without a GIS dependency so the adapter remains lightweight.
    """
    def inside(poly: str) -> bool:
        pts = []
        for token in re.split(r"\s+", poly.strip()):
            try:
                a, b = token.split(",")
                pts.append((float(a), float(b)))  # CAP: lat,lon
            except Exception:
                pass
        if len(pts) < 3: return False
        hit = False
        j = len(pts)-1
        for i,(yi,xi) in enumerate(pts):
            yj,xj=pts[j]
            if ((xi > lon) != (xj > lon)) and (lat < (yj-yi)*(lon-xi)/(xj-xi+1e-12)+yi): hit=not hit
            j=i
        return hit
    severity_score = {"extreme": .95, "severe": .75, "moderate": .50, "minor": .25}
    best = 0.0; matched = None
    for a in alerts:
        if a.get("polygon") and inside(a["polygon"]):
            s = severity_score.get(a.get("severity", "").lower(), .35)
            if s > best: best, matched = s, a
    return best, matched


def nrsc_metadata() -> dict:
    """Metadata for the NRSC/ISRO landslide layer used by the application."""
    return {
        "provider": "NRSC/ISRO Bhuvan",
        "enabled": True,
        "role": "Official hazard/inventory visualization",
        "layer": NRSC_LANDSLIDE_LAYER,
        "wms_url": NRSC_WMS_URL,
        "geojson_configured": bool(NRSC_LANDSLIDE_GEOJSON),
        "route_scoring_enabled": bool(NRSC_LANDSLIDE_GEOJSON),
        "note": (
            "NRSC/ISRO Bhuvan is used as hazard context. Server-side NRSC "
            "route scoring is enabled only when a genuine exported NRSC "
            "GeoJSON is configured. The historical Landslide Atlas is not "
            "treated as a live road-closure feed."
        ),
    }


def load_nrsc_geojson() -> dict | None:
    """Load optional locally downloaded NRSC GeoJSON and return it.

    NRSC exposes many products through Bhuvan WMS; public machine-readable
    route-level vector access is not guaranteed. Users may set
    NRSC_LANDSLIDE_GEOJSON to an exported NRSC GeoJSON/Shapefile-converted file.
    """
    if not NRSC_LANDSLIDE_GEOJSON or not os.path.exists(NRSC_LANDSLIDE_GEOJSON): return None
    try:
        import json
        with open(NRSC_LANDSLIDE_GEOJSON, encoding="utf-8") as f: return json.load(f)
    except Exception as exc:
        log.warning("Could not load NRSC GeoJSON: %s", exc)
        return None
