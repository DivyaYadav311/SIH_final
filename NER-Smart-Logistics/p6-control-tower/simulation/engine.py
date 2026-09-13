"""What-if impact model using live P5 shipments and P4 routing responses."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from p6_src.config import SNAPSHOT_DIR
from p6_src.ids import utc_now_iso
from simulation import clients as sim_clients

INACTIVE_STATUSES = {"DELIVERED", "CANCELLED"}


def _load_json(name: str) -> Any:
    path = SNAPSHOT_DIR / name
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_shipments() -> tuple[list[dict[str, Any]], str]:
    live = sim_clients.fetch_p5_shipments()
    if live and len(live) > 0:
        return live, "p5_http_live"
    snap = _load_json("shipments.json") or []
    if snap:
        return snap, "snapshot"
    return [], "p5_unavailable"


def load_simulation_shipments() -> tuple[list[dict[str, Any]], str, str | None]:
    live = sim_clients.fetch_p5_shipments()
    if live is None:
        return [], "p5_unavailable", "Unable to retrieve simulation results. Please check the P6 service."
    if len(live) > 0:
        return live, "p5_http_live", None
    return [], "p5_empty", None


def load_routes() -> dict[str, Any]:
    data = _load_json("routes.json") or {}
    if isinstance(data, list):
        return {r["route_id"]: r for r in data if r.get("route_id")}
    return data


def load_alternatives() -> dict[str, str]:
    data = _load_json("alternatives.json") or {}
    return {str(k): str(v) for k, v in data.items()}


def _destination_district(shipment: dict[str, Any]) -> str:
    return str(shipment.get("destination") or shipment.get("district_id") or shipment.get("to_location") or "")


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def _normalize_token(value: Any) -> str:
    return "".join(ch for ch in str(value).upper() if ch.isalnum())


def _parse_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _road_ids_from(payload: dict[str, Any] | None) -> list[str]:
    if not payload:
        return []
    raw = payload.get("road_ids") or payload.get("route") or []
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        return [str(item) for item in raw if item not in (None, "")]
    return []


def _uses_blocked_road(blocked: str, shipment: dict[str, Any], route: dict[str, Any] | None) -> bool:
    needle = _normalize_token(blocked)
    if not needle:
        return False
    haystacks: list[str] = []
    haystacks.extend(_road_ids_from(shipment))
    haystacks.extend(_road_ids_from(route))
    for key in ("route_id", "road_id"):
        if shipment.get(key):
            haystacks.append(str(shipment.get(key)))
        if route and route.get(key):
            haystacks.append(str(route.get(key)))
    return any(needle in _normalize_token(item) or _normalize_token(item) in needle for item in haystacks if item)


def _pair_key(origin: Any, destination: Any) -> tuple[str, str]:
    return (str(origin or "").strip(), str(destination or "").strip())


def _extract_coordinates(payload: dict[str, Any] | None) -> list[list[float]] | None:
    if not payload:
        return None
    coords = payload.get("route_coordinates")
    if not isinstance(coords, list) or len(coords) < 2:
        return None
    cleaned: list[list[float]] = []
    for point in coords:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            continue
        lat = _finite_number(point[0])
        lng = _finite_number(point[1])
        if lat is None or lng is None:
            continue
        cleaned.append([lat, lng])
    return cleaned if len(cleaned) >= 2 else None


def _passthrough_route(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not payload:
        return None
    keys = (
        "route_id",
        "origin",
        "destination",
        "road_ids",
        "route",
        "route_coordinates",
        "distance_km",
        "estimated_travel_time_minutes",
        "eta_hours",
        "duration_hours",
        "duration_formatted",
        "route_risk",
        "risk_level",
        "safety_score",
        "alternative_routes_available",
        "alternatives",
        "status",
    )
    out = {key: payload[key] for key in keys if key in payload and payload[key] is not None}
    return out or None


def _reroute_from_p4(current: dict[str, Any] | None, alternative: dict[str, Any] | None) -> dict[str, Any] | None:
    alt = _passthrough_route(alternative)
    if not alt:
        return None
    origin = alt.get("origin")
    destination = alt.get("destination")
    if origin and destination:
        alt["corridor"] = f"{origin} → {destination}"
    elif alt.get("road_ids"):
        alt["corridor"] = ", ".join(str(item) for item in alt["road_ids"])
    current_distance = _finite_number((current or {}).get("distance_km"))
    alt_distance = _finite_number(alt.get("distance_km"))
    if current_distance is not None and alt_distance is not None:
        alt["additional_distance_km"] = round(alt_distance - current_distance, 1)
    current_time = _finite_number((current or {}).get("estimated_travel_time_minutes"))
    alt_time = _finite_number(alt.get("estimated_travel_time_minutes"))
    if current_time is not None and alt_time is not None:
        alt["additional_time_hours"] = round((alt_time - current_time) / 60.0, 1)
    return alt


def run_what_if(scenario_type: str, road_id: str | None, warehouse_id: str | None) -> dict[str, Any]:
    shipments, shipment_source, shipment_error = load_simulation_shipments()
    blocked = (road_id or "").strip() or None
    errors: list[str] = []
    if shipment_error:
        errors.append(shipment_error)

    route_cache: dict[tuple[str, str, str], dict[str, Any] | None] = {}

    def cached_route(origin: Any, destination: Any, mode: str, shipment: dict[str, Any]) -> dict[str, Any] | None:
        key = (*_pair_key(origin, destination), mode)
        if not key[0] or not key[1]:
            return None
        if key not in route_cache:
            avoid = True if mode == "alternative" else False
            route_cache[key] = sim_clients.request_p4_route(
                origin,
                destination,
                cargo_type=shipment.get("cargo_type") or shipment.get("cargo"),
                priority=shipment.get("priority"),
                avoid_high_risk_roads=avoid,
            )
            if route_cache[key] is None:
                errors.append(f"P4 routing unavailable for {key[0]} → {key[1]} ({mode}).")
        return route_cache[key]

    affected: list[dict[str, Any]] = []
    current_by_id: dict[str, dict[str, Any] | None] = {}
    alternative_by_id: dict[str, dict[str, Any] | None] = {}

    if scenario_type == "WAREHOUSE_OUTAGE" and warehouse_id:
        for shipment in shipments:
            origin = str(shipment.get("origin_warehouse_id") or shipment.get("origin") or "")
            if warehouse_id in origin or origin == warehouse_id:
                affected.append(shipment)
    else:
        for shipment in shipments:
            origin = shipment.get("origin")
            destination = shipment.get("destination")
            current = cached_route(origin, destination, "current", shipment)
            shipment_id = str(shipment.get("shipment_id") or id(shipment))
            current_by_id[shipment_id] = current
            if blocked and _uses_blocked_road(blocked, shipment, current):
                affected.append(shipment)
                alternative_by_id[shipment_id] = cached_route(origin, destination, "alternative", shipment)

    delayed = [s for s in affected if str(s.get("status") or "").upper() not in INACTIVE_STATUSES]
    districts = {_destination_district(s) for s in affected if _destination_district(s)}

    shipments_detail: list[dict[str, Any]] = []
    delay_minutes_samples: list[float] = []
    for shipment in delayed:
        shipment_id = str(shipment.get("shipment_id") or id(shipment))
        current = current_by_id.get(shipment_id)
        alternative = alternative_by_id.get(shipment_id)
        orig_min = _finite_number((current or {}).get("estimated_travel_time_minutes"))
        if orig_min is None:
            orig_min = _finite_number(shipment.get("estimated_travel_time_minutes"))
        alt_min = _finite_number((alternative or {}).get("estimated_travel_time_minutes"))
        delay_min = (alt_min - orig_min) if orig_min is not None and alt_min is not None else None
        if delay_min is not None:
            delay_minutes_samples.append(delay_min)

        current_eta = (
            shipment.get("estimated_arrival")
            or shipment.get("current_eta")
            or shipment.get("requested_delivery")
        )
        current_dt = _parse_datetime(current_eta)
        revised_eta = None
        if current_dt is not None and delay_min is not None:
            revised_eta = (current_dt + timedelta(minutes=delay_min)).isoformat()

        detail: dict[str, Any] = {
            "shipment_id": shipment.get("shipment_id"),
            "priority": shipment.get("priority"),
            "cargo": shipment.get("cargo") or shipment.get("cargo_type"),
            "origin": shipment.get("origin"),
            "destination": shipment.get("destination"),
            "status": shipment.get("status"),
            "route_id": shipment.get("route_id"),
            "current_eta": current_dt.isoformat() if current_dt else current_eta,
            "revised_eta": revised_eta,
            "delay_hours": round(delay_min / 60.0, 1) if delay_min is not None else None,
        }
        shipments_detail.append(detail)

    reroute = None
    route_coordinates = None
    recommended_route_id = None
    for shipment in delayed:
        shipment_id = str(shipment.get("shipment_id") or id(shipment))
        candidate = _reroute_from_p4(current_by_id.get(shipment_id), alternative_by_id.get(shipment_id))
        if not candidate:
            continue
        reroute = candidate
        recommended_route_id = candidate.get("route_id")
        route_coordinates = _extract_coordinates(candidate)
        if route_coordinates:
            break
    if reroute and route_coordinates is None:
        route_coordinates = _extract_coordinates(reroute)

    average_delay_minutes = (
        round(sum(delay_minutes_samples) / len(delay_minutes_samples))
        if delay_minutes_samples
        else None
    )

    unique_errors = list(dict.fromkeys(errors))
    provenance = {
        "shipments": shipment_source,
        "routing_engine": "p4_http_live" if any(route_cache.values()) else "p4_unavailable",
        "scenario": scenario_type,
    }

    return {
        "scenario_type": scenario_type,
        "road_id": blocked,
        "affected_roads": [blocked] if blocked else [],
        "affected_shipments": len(affected),
        "delayed_shipments": len(delayed),
        "affected_districts": len(districts),
        "additional_delay_minutes": average_delay_minutes,
        "average_delay_hours": round(average_delay_minutes / 60.0, 1) if average_delay_minutes is not None else None,
        "shortage_risk_change": None,
        "recommended_route_id": recommended_route_id,
        "recommended_reroutes": [reroute] if reroute else [],
        "alternative_route": reroute,
        "route_coordinates": route_coordinates,
        "affected_shipments_detail": shipments_detail,
        "generated_at": utc_now_iso(),
        "data_provenance": provenance,
        "errors": unique_errors,
    }
