"""Conservative, auditable historical-event to OSM-way matching."""
from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

DEFAULT_PBF = Path(__file__).resolve().parents[2] / "data" / "raw" / "roads" / "india-latest.osm.pbf"
EXCLUDED_HIGHWAYS = {"footway", "path", "cycleway", "steps", "pedestrian"}
ROAD_WORDS = {"road", "rd", "street", "st", "highway", "hwy", "route", "marg"}
NARRATIVE_WORDS = {"blocked", "damaged", "damage", "electric", "pole", "vegetation", "washed", "out", "closed", "disrupted", "connectivity", "house", "crest", "partially"}
GENERIC_TOKENS = ROAD_WORDS | {"the", "and", "towards", "from", "to", "on", "of"}
LAST_PBF_STATS: dict[str, int | bool] = {"ways_examined": 0, "candidate_ways": 0, "parser_available": False}


def normalize_highway_ref(value: str | None) -> str | None:
    """Normalize only explicit NH/SH references; never infer a number."""
    text = str(value or "").upper()
    match = re.search(r"\b(?:NATIONAL\s*HIGHWAY|NH)\s*[-./ ]*([0-9]+[A-Z]?)\b", text)
    if match:
        return f"NH-{match.group(1)}"
    match = re.search(r"\b(?:STATE\s*HIGHWAY|SH)\s*[-./ ]*([0-9]+[A-Z]?)\b", text)
    return f"SH-{match.group(1)}" if match else None


def normalize_road_name(value: str | None) -> str | None:
    if not value or not str(value).strip():
        return None
    explicit_ref = normalize_highway_ref(value)
    if explicit_ref:
        return explicit_ref
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()) or None


def road_identity(event: dict[str, Any]) -> dict[str, Any]:
    raw_text = str(event.get("road_name") or "").strip()
    explicit = normalize_highway_ref(event.get("highway_number")) or normalize_highway_ref(raw_text)
    normalized = normalize_road_name(raw_text)
    tokens = set(re.findall(r"[a-z0-9]+", raw_text.lower()))
    hits = sorted(tokens & NARRATIVE_WORDS)
    if not raw_text:
        quality, evidence = "EMPTY", ["road_name is empty"]
    elif explicit:
        quality, evidence = "VALID", [f"explicit highway reference {explicit}"]
    elif hits and (len(hits) >= 2 or raw_text.lower().startswith(("road blocked", "road damaged"))):
        quality, evidence, normalized = "NARRATIVE_TEXT", [f"incident-language tokens: {', '.join(hits)}"], None
    elif len(tokens - GENERIC_TOKENS) >= 2 and (tokens & ROAD_WORDS or "-" in raw_text):
        quality, evidence = "VALID", ["named road-style text"]
    else:
        quality, evidence = "UNCERTAIN", ["not an explicit highway reference or sufficiently specific road name"]
    return {"road_name_raw": raw_text or None, "road_name_normalized": normalized, "road_name_quality": quality,
            "extracted_highway_ref": explicit, "identity_evidence": evidence}


def _tokens(value: str | None) -> set[str]:
    return {x for x in re.findall(r"[a-z0-9]+", str(value or "").lower()) if x not in GENERIC_TOKENS and len(x) > 1}


def _name_similarity(left: str | None, right: str | None) -> float:
    a, b = _tokens(left), _tokens(right)
    return round(len(a & b) / len(a | b), 4) if a and b else 0.0


def validate_geometry(geometry: list[dict[str, float]] | None) -> bool:
    return bool(geometry and len(geometry) >= 2 and all(isinstance(p.get("lat"), (int, float)) and isinstance(p.get("lon"), (int, float)) and -90 <= p["lat"] <= 90 and -180 <= p["lon"] <= 180 for p in geometry))


def _point_segment_distance_m(lat: float, lon: float, a: dict[str, float], b: dict[str, float]) -> float:
    sx = 111_320 * math.cos(math.radians(lat)); ax, ay = (a["lon"] - lon) * sx, (a["lat"] - lat) * 111_320; bx, by = (b["lon"] - lon) * sx, (b["lat"] - lat) * 111_320
    dx, dy = bx - ax, by - ay; denom = dx * dx + dy * dy
    frac = max(0.0, min(1.0, -(ax * dx + ay * dy) / denom)) if denom else 0.0
    return math.hypot(ax + frac * dx, ay + frac * dy)


def _distance_m(latitude: float, longitude: float, geometry: list[dict[str, float]]) -> float | None:
    return round(min(_point_segment_distance_m(latitude, longitude, a, b) for a, b in zip(geometry, geometry[1:])), 2) if validate_geometry(geometry) else None


def _could_be_near(latitude: float, longitude: float, geometry: list[dict[str, float]], radius_m: int) -> bool:
    """Cheap bounding-box rejection before segment-distance calculations."""
    lat_pad = radius_m / 111_320
    lon_pad = radius_m / max(111_320 * math.cos(math.radians(latitude)), 1)
    lats = [p["lat"] for p in geometry]; lons = [p["lon"] for p in geometry]
    return min(lats) - lat_pad <= latitude <= max(lats) + lat_pad and min(lons) - lon_pad <= longitude <= max(lons) + lon_pad


def _road_type_agreement(event: dict[str, Any], highway: str | None) -> bool | None:
    if not highway or not event.get("road_type"):
        return None
    return highway in {"motorway", "trunk", "primary", "secondary"} if str(event["road_type"]).lower() == "highway" else True


def _score_candidate(event: dict[str, Any], element: dict[str, Any]) -> dict[str, Any]:
    identity, tags, geometry = road_identity(event), element.get("tags") or {}, element.get("geometry") or []
    highway, valid, distance = tags.get("highway"), validate_geometry(geometry), element.get("distance_from_event")
    candidate_ref = normalize_highway_ref(tags.get("ref")); ref_match = bool(identity["extracted_highway_ref"] and candidate_ref == identity["extracted_highway_ref"])
    similarity = _name_similarity(identity["road_name_normalized"] if identity["road_name_quality"] == "VALID" else None, tags.get("name"))
    rejection = f"excluded non-road highway={highway}" if highway in EXCLUDED_HIGHWAYS else "invalid_geometry" if not valid else "distance_unavailable" if distance is None else None
    score = round((100 if ref_match else 0) + similarity * 60 + max(0, 25 - float(distance or 999) / 12), 2)
    confidence = "high" if (ref_match or similarity >= .85) and valid and distance is not None and distance <= 100 else "medium" if (ref_match or similarity >= .5) and valid else "low"
    return {"osm_way_id": str(element["id"]), "name": tags.get("name"), "ref": tags.get("ref"), "highway": highway, "distance_m": distance,
            "geometry_valid": valid, "name_similarity": similarity, "ref_match": ref_match, "highway_class": highway, "candidate_score": score,
            "rejection_reason": rejection, "geometry": [[p["lon"], p["lat"]] for p in geometry] if valid else [], "tags": tags,
            "road_type_agreement": _road_type_agreement(event, highway), "matching_confidence": confidence,
            "road_name_agreement": similarity > 0, "ref_agreement": ref_match, "geometry_available": valid}


def _select(event: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    plausible = sorted((c for c in candidates if c["rejection_reason"] is None), key=lambda c: (c["distance_m"], c["osm_way_id"]))
    nearest, second = (plausible[0] if plausible else None), (plausible[1] if len(plausible) > 1 else None)
    near, second_d = (nearest["distance_m"] if nearest else None), (second["distance_m"] if second else None)
    gap = round(second_d - near, 2) if second else None
    identity = sorted((c for c in plausible if c["ref_match"] or c["name_similarity"] >= .5), key=lambda c: (-c["ref_match"], -c["name_similarity"], c["distance_m"], c["osm_way_id"]))
    status, selected, reason = "NO_RELIABLE_MATCH", None, "no valid road geometry within search radius"
    if identity:
        top = identity[0]; tied = len(identity) > 1 and identity[1]["candidate_score"] >= top["candidate_score"] - 5
        if tied: status, reason = "AMBIGUOUS", "multiple candidates have similar road-identity evidence"
        elif top["ref_match"] or (top["name_similarity"] >= .85 and top["distance_m"] <= 100): status, selected, reason = "HIGH_CONFIDENCE", top, "explicit reference or strong normalized road-name agreement with valid geometry"
        else: status, selected, reason = "MEDIUM_CONFIDENCE", top, "partial road-identity agreement; human review required"
    elif nearest:
        if near <= 40 and (second is None or gap >= 150): status, selected, reason = "MEDIUM_CONFIDENCE", nearest, "isolated nearby road from coordinate evidence only; human review required"
        elif len(plausible) > 1: status, reason = "AMBIGUOUS", "several plausible nearby roads; coordinate evidence cannot select one"
        else: status, reason = "COORDINATE_FALLBACK", "only an unverified coordinate buffer is available"
    return {"match_status": status, "selected_candidate": selected, "match_reason": reason, "nearest_candidate_distance": near,
            "second_nearest_candidate_distance": second_d, "distance_gap": gap, "candidate_count": len(plausible),
            "number_of_distinct_road_classes": len({c["highway_class"] for c in plausible}), "distinct_road_classes": sorted({c["highway_class"] for c in plausible})}


def match_local_pbf_events(events: list[dict[str, Any]], radius_m: int = 300) -> dict[str, dict[str, Any]]:
    """Stream the PBF once and preserve every highway candidate within radius."""
    try:
        import osmium  # type: ignore
    except ImportError as error:
        LAST_PBF_STATS.update({"ways_examined": 0, "candidate_ways": 0, "parser_available": False})
        return {str(e["event_id"]): {**_fallback(e, "COORDINATE_FALLBACK", str(error)), **road_identity(e), "all_candidates": []} for e in events}
    if not DEFAULT_PBF.exists():
        LAST_PBF_STATS.update({"ways_examined": 0, "candidate_ways": 0, "parser_available": True})
        return {str(e["event_id"]): {**_fallback(e, "COORDINATE_FALLBACK", "local_pbf_missing"), **road_identity(e), "all_candidates": []} for e in events}
    class Handler(osmium.SimpleHandler):
        def __init__(self): super().__init__(); self.candidates = {str(e["event_id"]): [] for e in events}; self.ways_examined = 0
        def way(self, way: Any) -> None:
            tags = dict(way.tags)
            if not tags.get("highway"): return
            self.ways_examined += 1; geometry = [{"lat": n.lat, "lon": n.lon} for n in way.nodes]
            if not geometry: return
            for event in events:
                if not _could_be_near(float(event["latitude"]), float(event["longitude"]), geometry, radius_m): continue
                distance = _distance_m(float(event["latitude"]), float(event["longitude"]), geometry)
                if distance is not None and distance <= radius_m: self.candidates[str(event["event_id"])].append({"id": way.id, "tags": tags, "geometry": geometry, "distance_from_event": distance})
    handler = Handler(); handler.apply_file(str(DEFAULT_PBF), locations=True)
    LAST_PBF_STATS.update({"ways_examined": handler.ways_examined, "candidate_ways": sum(map(len, handler.candidates.values())), "parser_available": True})
    output = {}
    for event in events:
        candidates = sorted((_score_candidate(event, c) for c in handler.candidates[str(event["event_id"])]), key=lambda c: (c["distance_m"], c["osm_way_id"]))
        decision = _select(event, candidates); selected = decision.pop("selected_candidate")
        output[str(event["event_id"])] = {**road_identity(event), **decision, "all_candidates": candidates, "geometry_source": "osm_local_pbf" if selected else "coordinate_buffer", "matching_confidence": decision["match_status"], "osm_way_id": selected["osm_way_id"] if selected else None, "osm_road_name": selected["name"] if selected else None, "osm_ref": selected["ref"] if selected else None, "osm_highway_type": selected["highway"] if selected else None, "distance_from_event": selected["distance_m"] if selected else None, "geometry": selected["geometry"] if selected else [], "matching_method": "local_pbf_identity_and_coordinate_audit"}
    return output


def _fallback(event: dict[str, Any], reason: str, error: str | None) -> dict[str, Any]:
    return {"geometry_source": "coordinate_buffer", "match_status": reason, "match_reason": reason, "failure_reason": reason, "error": error, "osm_way_id": None, "osm_road_name": None, "osm_ref": None, "osm_highway_type": None, "distance_from_event": None, "geometry": [], "matching_method": "none", "matching_confidence": reason}


def find_osm_road(event: dict[str, Any], cache_dir: str | Path, radius_m: int = 300) -> dict[str, Any]:
    return match_local_pbf_events([event], radius_m)[str(event["event_id"])]
