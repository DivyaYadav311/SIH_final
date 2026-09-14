"""What-if impact model using P5 shipment data and P4 route responses."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from p6_src.ids import utc_now_iso
from simulation import clients


def load_shipments() -> tuple[list[dict[str, Any]], str]:
    live = clients.fetch_p5_shipments()

    # None = P5 unavailable
    # [] = P5 available and currently has zero shipments
    if live is not None:
        return live, "p5_http_live"

    return [], "unavailable"


def load_routes(shipments: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Resolve route data for shipments from P4 routing service or embedded route records."""
    routes: dict[str, Any] = {}
    if not shipments:
        return routes

    for shipment in shipments:
        embedded = shipment.get("route")
        if isinstance(embedded, dict) and embedded.get("road_ids"):
            route_id = str(shipment.get("route_id") or embedded.get("route_id") or id(embedded))
            routes[route_id] = embedded
            continue

        origin = shipment.get("origin")
        destination = shipment.get("destination")
        route_id = str(shipment.get("route_id") or "")

        cache_key = f"{origin}::{destination}"
        if cache_key in routes:
            if route_id:
                routes[route_id] = routes[cache_key]
            continue

        if origin and destination:
            p4_route = clients.fetch_p4_route(
                origin,
                destination,
                cargo_type=str(shipment.get("cargo_type") or shipment.get("cargo") or "") or None,
                priority=str(shipment.get("priority") or "") or None,
                transport_mode=str(shipment.get("transport_mode") or "") or None,
            )
            if p4_route:
                routes[cache_key] = p4_route
                p4_rid = str(p4_route.get("route_id") or "")
                if p4_rid:
                    routes[p4_rid] = p4_route
                if route_id:
                    routes[route_id] = p4_route

    return routes


def _road_matches(blocked: str, road: str) -> bool:
    b = (blocked or "").strip().upper()
    r = (road or "").strip().upper()
    if not b or not r:
        return False
    if b == r:
        return True
    b_norm = b.replace(" ", "").replace("-", "")
    r_norm = r.replace(" ", "").replace("-", "")
    if b_norm == r_norm:
        return True
    if b in r or b_norm in r_norm:
        return True
    return False


def _destination_district(shipment: dict[str, Any]) -> str:
    return str(shipment.get("destination") or shipment.get("district_id") or shipment.get("to_location") or "")


def _route_for_shipment(shipment: dict[str, Any], routes: dict[str, Any]) -> dict[str, Any]:
    embedded = shipment.get("route")
    if isinstance(embedded, dict):
        return embedded
    route_id = str(shipment.get("route_id") or "")
    if route_id and isinstance(routes.get(route_id), dict):
        return routes[route_id]
    origin = str(shipment.get("origin") or "")
    dest = str(shipment.get("destination") or "")
    cache_key = f"{origin}::{dest}"
    if cache_key in routes and isinstance(routes[cache_key], dict):
        return routes[cache_key]
    return {}


def _route_road_ids(shipment: dict[str, Any], routes: dict[str, Any]) -> list[str]:
    if isinstance(shipment.get("road_ids"), list):
        return [str(road_id) for road_id in shipment["road_ids"] if road_id]
    route = _route_for_shipment(shipment, routes)
    road_ids = route.get("road_ids") or []
    if isinstance(road_ids, list):
        return [str(road_id) for road_id in road_ids if road_id]
    return []


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
    current_eta_raw = shipment.get("current_eta") or shipment.get("estimated_arrival")
    if current_eta_raw:
        public["current_eta"] = current_eta_raw

    if delay_minutes is not None:
        public["delay_minutes"] = delay_minutes
        public["delay_hours"] = round(delay_minutes / 60.0, 1)
        if current_eta_raw:
            try:
                dt_str = str(current_eta_raw).replace("Z", "+00:00")
                c_dt = datetime.fromisoformat(dt_str)
                public["revised_eta"] = (c_dt + timedelta(minutes=delay_minutes)).isoformat()
            except Exception:
                public["revised_eta"] = None
        else:
            public["revised_eta"] = None
    else:
        public["delay_minutes"] = None
        public["delay_hours"] = None
        public["revised_eta"] = None
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

        replacement = clients.request_p4_alternative(
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

        current_dist = current_route.get("distance_km")
        replacement_dist = replacement.get("distance_km")
        if isinstance(current_dist, (int, float)) and isinstance(replacement_dist, (int, float)):
            replacement["additional_distance_km"] = max(0.0, round(float(replacement_dist) - float(current_dist), 1))

    if not first_route:
        return None, None, None

    avg_delay = None
    if delay_values:
        avg_delay = int(round(sum(delay_values) / len(delay_values)))

    route_id = first_route.get("route_id")
    return first_route, avg_delay, str(route_id) if route_id else None


KNOWN_CORRIDORS: dict[str, tuple[str, str]] = {
    "NH-13": ("Tezpur", "Tawang"),
    "NH-27": ("Guwahati", "Silchar"),
    "NH-6": ("Guwahati", "Shillong"),
    "NH-15": ("Guwahati", "Tezpur"),
    "NH-29": ("Dimapur", "Kohima"),
    "NH-102": ("Imphal", "Moreh"),
    "NH-306": ("Silchar", "Aizawl"),
    "NH-310": ("Gangtok", "Nathu La"),
    "GS-ROAD": ("Guwahati", "Shillong"),
    "SELA-PASS-ROAD": ("Tezpur", "Tawang"),
    "ROAD_102": ("Guwahati", "Tawang"),
}


def _resolve_corridor_endpoints(road_id: str, routes: dict[str, Any]) -> tuple[str | dict[str, float], str | dict[str, float]] | None:
    blocked_clean = (road_id or "").strip().upper()
    if not blocked_clean:
        return None

    for cid, endpoints in KNOWN_CORRIDORS.items():
        if _road_matches(blocked_clean, cid):
            return endpoints

    # Check loaded routes
    for r in routes.values():
        if not isinstance(r, dict):
            continue
        r_roads = r.get("road_ids") or []
        if any(_road_matches(blocked_clean, rid) for rid in r_roads):
            orig = r.get("origin") or r.get("origin_coords")
            dest = r.get("destination") or r.get("destination_coords")
            if orig and dest:
                return (orig, dest)

    return None


def run_what_if(scenario_type: str, road_id: str | None, warehouse_id: str | None) -> dict[str, Any]:
    shipments, shipment_source = load_shipments()
    routes = load_routes(shipments)
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
            if blocked and any(_road_matches(blocked, rid) for rid in road_ids):
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
    has_resolved_routes = bool(routes)
    shipment_route_data_available = has_resolved_routes or any(
        isinstance(shipment.get("route"), dict) or isinstance(shipment.get("road_ids"), list)
        for shipment in affected
    )
    provenance = {
        "shipments": shipment_source,
        "routes": "p4_http" if has_resolved_routes else ("p5_shipments" if shipment_route_data_available else "unavailable"),
        "scenario": scenario_type,
    }

    if "unavailable" in shipment_source:
        unavailable_metrics.append("shipments")

    if blocked and delayed:
        recommended_route, delay, recommended_route_id = _find_replacement_route(delayed, routes)
        if recommended_route:
            route_geometry = _route_geometry(recommended_route)
            provenance["recommended_route"] = "p4_http"
            provenance["routes"] = "p4_http"
            if delay is None:
                unavailable_metrics.append("additional_delay_minutes")
        else:
            unavailable_metrics.extend(["recommended_route", "route_geometry", "additional_delay_minutes"])
    elif blocked:
        # Decoupled network disruption simulation:
        # Obtain real corridor endpoints to query P4 for an alternative route
        endpoints = _resolve_corridor_endpoints(blocked, routes)
        if endpoints:
            orig, dest = endpoints
            # Call P4 alternative route avoiding high-risk roads
            replacement = clients.request_p4_alternative(orig, dest)
            if replacement:
                recommended_route = replacement
                route_id = replacement.get("route_id")
                recommended_route_id = str(route_id) if route_id else None
                route_geometry = _route_geometry(replacement)
                provenance["recommended_route"] = "p4_http"
                provenance["routes"] = "p4_http"

                # If baseline route can be fetched, calculate honest delay and additional distance
                base_route = clients.fetch_p4_route(orig, dest)
                if base_route:
                    base_eta = _route_eta_minutes(base_route)
                    repl_eta = _route_eta_minutes(replacement)
                    if base_eta is not None and repl_eta is not None:
                        delay = max(0, int(round(repl_eta - base_eta)))

                    base_dist = base_route.get("distance_km")
                    repl_dist = replacement.get("distance_km")
                    if isinstance(base_dist, (int, float)) and isinstance(repl_dist, (int, float)):
                        replacement["additional_distance_km"] = max(0.0, round(float(repl_dist) - float(base_dist), 1))

                if delay is None:
                    unavailable_metrics.append("additional_delay_minutes")
            else:
                unavailable_metrics.extend(["recommended_route", "route_geometry", "additional_delay_minutes"])
        else:
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
        "route_coordinates": route_geometry,
        "affected_shipment_records": affected_records,
        "affected_shipments_detail": affected_detail,
        "unavailable_metrics": sorted(set(unavailable_metrics)),
        "generated_at": utc_now_iso(),
        "data_provenance": provenance,
    }