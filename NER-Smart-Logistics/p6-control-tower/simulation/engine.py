"""What-if impact model using P5 shipment data and P4 route responses."""
from __future__ import annotations

from typing import Any

from p6_src.ids import utc_now_iso
from simulation.clients import fetch_p5_shipments, request_p4_alternative


def load_shipments() -> tuple[list[dict[str, Any]], str]:
    live = fetch_p5_shipments()
    if live:
        return live, "p5_http"
    return [], "unavailable"


def load_routes() -> dict[str, Any]:
    return {}


def _destination_district(shipment: dict[str, Any]) -> str:
    return str(shipment.get("destination") or shipment.get("district_id") or shipment.get("to_location") or "")


def _route_for_shipment(shipment: dict[str, Any], routes: dict[str, Any]) -> dict[str, Any]:
    embedded = shipment.get("route")
    if isinstance(embedded, dict):
        return embedded
    route_id = shipment.get("route_id")
    if route_id and isinstance(routes.get(route_id), dict):
        return routes[route_id]
    return {}


def _route_road_ids(shipment: dict[str, Any], routes: dict[str, Any]) -> list[str]:
    route = _route_for_shipment(shipment, routes)
    road_ids = route.get("road_ids") or shipment.get("road_ids") or []
    return [str(road_id) for road_id in road_ids]


def _route_endpoint(value: Any) -> dict[str, float] | None:
    if not isinstance(value, dict):
        return None
    lat = value.get("latitude", value.get("lat"))
    lng = value.get("longitude", value.get("lng"))
    if isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
        return {"latitude": float(lat), "longitude": float(lng)}
    return None


def _shipment_endpoint(
    shipment: dict[str, Any],
    route: dict[str, Any],
    shipment_key: str,
    route_key: str,
) -> str | dict[str, float] | None:
    raw = shipment.get(shipment_key)
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return _route_endpoint(shipment.get(f"{shipment_key}_coords")) or _route_endpoint(route.get(route_key))


def _current_route_eta_minutes(shipment: dict[str, Any], route: dict[str, Any]) -> float | None:
    value = shipment.get("estimated_travel_time_minutes", route.get("estimated_travel_time_minutes"))
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _route_eta_minutes(route: dict[str, Any] | None) -> float | None:
    if not route:
        return None
    value = route.get("estimated_travel_time_minutes")
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _route_geometry(route: dict[str, Any] | None) -> list[list[float]] | None:
    if not route:
        return None
    coords = route.get("route_coordinates")
    if isinstance(coords, list) and coords:
        return coords
    return None


def _public_shipment(shipment: dict[str, Any]) -> dict[str, Any]:
    allowed = (
        "shipment_id",
        "origin",
        "destination",
        "cargo",
        "cargo_type",
        "quantity",
        "unit",
        "priority",
        "status",
        "route_id",
        "road_ids",
        "estimated_travel_time_minutes",
        "distance_km",
        "estimated_arrival",
        "current_eta",
        "shipment_risk",
        "route_risk",
        "district_id",
    )
    return {key: shipment[key] for key in allowed if key in shipment}


def _shipment_eta_fields(shipment: dict[str, Any], delay_minutes: int | None) -> dict[str, Any]:
    public = _public_shipment(shipment)
    if delay_minutes is not None:
        public["delay_minutes"] = delay_minutes
    return public


def _find_replacement_route(
    delayed: list[dict[str, Any]],
    routes: dict[str, Any],
) -> tuple[dict[str, Any] | None, int | None, str | None]:
    delay_values: list[int] = []
    first_route: dict[str, Any] | None = None

    for shipment in delayed:
        current_route = _route_for_shipment(shipment, routes)
        origin = _shipment_endpoint(shipment, current_route, "origin", "origin_coords")
        destination = _shipment_endpoint(shipment, current_route, "destination", "destination_coords")
        if origin is None or destination is None:
            continue

        replacement = request_p4_alternative(
            origin,
            destination,
            cargo_type=str(shipment.get("cargo_type") or shipment.get("cargo") or "") or None,
            priority=str(shipment.get("priority") or "") or None,
            transport_mode=str(shipment.get("transport_mode") or "") or None,
        )
        if not replacement:
            continue

        if first_route is None:
            first_route = replacement

        current_eta = _current_route_eta_minutes(shipment, current_route)
        replacement_eta = _route_eta_minutes(replacement)
        if current_eta is not None and replacement_eta is not None:
            delay_values.append(max(0, int(round(replacement_eta - current_eta))))

    if not first_route:
        return None, None, None

    avg_delay = None
    if delay_values:
        avg_delay = int(round(sum(delay_values) / len(delay_values)))

    route_id = first_route.get("route_id")
    return first_route, avg_delay, str(route_id) if route_id else None


def run_what_if(scenario_type: str, road_id: str | None, warehouse_id: str | None) -> dict[str, Any]:
    shipments, shipment_source = load_shipments()
    routes = load_routes()
    blocked = (road_id or "").strip()
    affected: list[dict[str, Any]] = []

    if scenario_type == "WAREHOUSE_OUTAGE" and warehouse_id:
        for shipment in shipments:
            origin = str(shipment.get("origin_warehouse_id") or shipment.get("origin") or "")
            if warehouse_id in origin or origin == warehouse_id:
                affected.append(shipment)
    else:
        for shipment in shipments:
            road_ids = _route_road_ids(shipment, routes)
            if blocked and blocked in road_ids:
                affected.append(shipment)

    delayed = [
        shipment
        for shipment in affected
        if str(shipment.get("status") or "").upper() not in ("DELIVERED", "CANCELLED")
    ]
    districts = {_destination_district(shipment) for shipment in affected if _destination_district(shipment)}

    recommended_route = None
    recommended_route_id = None
    delay = None
    route_geometry = None
    unavailable_metrics: list[str] = []
    shipment_route_data_available = any(
        isinstance(shipment.get("route"), dict) or isinstance(shipment.get("road_ids"), list)
        for shipment in affected
    )
    provenance = {
        "shipments": shipment_source,
        "routes": "p5_shipments" if shipment_route_data_available else "unavailable",
        "scenario": scenario_type,
    }

    if shipment_source == "unavailable":
        unavailable_metrics.append("shipments")

    if blocked and delayed:
        recommended_route, delay, recommended_route_id = _find_replacement_route(delayed, routes)
        if recommended_route:
            route_geometry = _route_geometry(recommended_route)
            provenance["recommended_route"] = "p4_http"
            if delay is None:
                unavailable_metrics.append("additional_delay_minutes")
        else:
            unavailable_metrics.extend(["recommended_route", "route_geometry", "additional_delay_minutes"])
    elif blocked:
        unavailable_metrics.extend(["recommended_route", "route_geometry", "additional_delay_minutes"])

    shortage_change = None
    if delayed:
        unavailable_metrics.append("shortage_risk_change")

    affected_records = [_public_shipment(shipment) for shipment in affected]
    affected_detail = [_shipment_eta_fields(shipment, delay) for shipment in delayed]

    return {
        "scenario_type": scenario_type,
        "road_id": blocked or None,
        "affected_roads": [blocked] if blocked else [],
        "affected_shipments": len(affected),
        "delayed_shipments": len(delayed),
        "affected_districts": len(districts),
        "additional_delay_minutes": delay,
        "average_delay_hours": round(delay / 60.0, 1) if delay is not None else None,
        "shortage_risk_change": shortage_change,
        "recommended_route_id": recommended_route_id,
        "recommended_route": recommended_route,
        "recommended_reroutes": [recommended_route] if recommended_route else [],
        "route_geometry": route_geometry,
        "affected_shipment_records": affected_records,
        "affected_shipments_detail": affected_detail,
        "unavailable_metrics": sorted(set(unavailable_metrics)),
        "generated_at": utc_now_iso(),
        "data_provenance": provenance,
    }
