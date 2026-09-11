"""
Pydantic request / response models for the route-optimization API.

Supports BOTH input formats the team uses:

  Format 1 — coordinates:
    {"origin": {"latitude": 26.14, "longitude": 91.74},
     "destination": {"latitude": 27.59, "longitude": 91.86}, ...}

  Format 2 — place names:
    {"source": "Guwahati", "destination": "Tawang", ...}
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Optional

from pydantic import BaseModel, model_validator


# ─────────────────────────────────────────────────────────────────────────
#  Request
# ─────────────────────────────────────────────────────────────────────────
class RouteRequest(BaseModel):
    """Flexible route request — parsed from arbitrary JSON via validator."""

    origin_lat: Optional[float] = None
    origin_lng: Optional[float] = None
    dest_lat: Optional[float] = None
    dest_lng: Optional[float] = None
    source_name: Optional[str] = None
    dest_name: Optional[str] = None
    departure_date: Optional[str] = None
    departure_time: Optional[str] = None
    cargo_type: str = "general"
    priority: str = "medium"
    transport_mode: str = "road"
    avoid_high_risk_roads: bool = True
    max_vehicle_weight_tons: float = 10.0
    goal: str = "safest"

    @model_validator(mode="before")
    @classmethod
    def parse_flexible_input(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        out: dict[str, Any] = {}
        out["departure_date"] = data.get("departure_date")
        out["departure_time"] = data.get("departure_time")

        # ── origin / source ──
        origin = data.get("origin") or data.get("origin_query") or data.get("source_name") or data.get("source") or data.get("source_query")
        source = data.get("source") or data.get("source_query") or data.get("source_name")
        if isinstance(origin, dict):
            out["origin_lat"] = origin.get("latitude") if origin.get("latitude") is not None else origin.get("lat")
            out["origin_lng"] = origin.get("longitude") if origin.get("longitude") is not None else origin.get("lng")
            if origin.get("name"):
                out["source_name"] = origin.get("name")
        elif isinstance(origin, str):
            out["source_name"] = origin
        if isinstance(source, str):
            out["source_name"] = source
        if data.get("source_name") and not out.get("source_name"):
            out["source_name"] = data.get("source_name")
        if data.get("origin_lat") is not None:
            out["origin_lat"] = float(data["origin_lat"])
        if data.get("origin_lng") is not None:
            out["origin_lng"] = float(data["origin_lng"])

        # ── destination (dict or string) ──
        dest = data.get("destination") or data.get("dest") or data.get("dest_query") or data.get("dest_name") or data.get("destination_name")
        if isinstance(dest, dict):
            out["dest_lat"] = dest.get("latitude") if dest.get("latitude") is not None else dest.get("lat")
            out["dest_lng"] = dest.get("longitude") if dest.get("longitude") is not None else dest.get("lng")
            if dest.get("name"):
                out["dest_name"] = dest.get("name")
        elif isinstance(dest, str):
            out["dest_name"] = dest
        if data.get("dest_name") and not out.get("dest_name"):
            out["dest_name"] = data.get("dest_name")
        if data.get("dest_lat") is not None:
            out["dest_lat"] = float(data["dest_lat"])
        if data.get("dest_lng") is not None:
            out["dest_lng"] = float(data["dest_lng"])

        # ── scalar fields ──
        out["cargo_type"] = data.get("cargo_type", "general").lower()
        out["priority"] = data.get("priority", "medium").lower()
        out["transport_mode"] = data.get("transport_mode", "road").lower()
        out["goal"] = data.get("goal", "safest").lower()

        # ── nested constraints (optional) ──
        constraints = data.get("constraints")
        if isinstance(constraints, dict):
            out["avoid_high_risk_roads"] = constraints.get(
                "avoid_high_risk_roads", True
            )
            out["max_vehicle_weight_tons"] = constraints.get(
                "max_vehicle_weight_tons", 10.0
            )
            if "transport_mode" in constraints:
                out["transport_mode"] = constraints.get("transport_mode", "road").lower()

        return out


# ─────────────────────────────────────────────────────────────────────────
#  Response
# ─────────────────────────────────────────────────────────────────────────
class RouteResponse(BaseModel):
    route_id: str
    origin: str
    destination: str
    transport_mode: Optional[str] = "road"
    transit_modes: Optional[List[str]] = None
    road_ids: List[str]
    route: Optional[List[str]] = None
    waypoints: Optional[List[Any]] = None
    route_coordinates: Optional[List[List[float]]] = None
    navigation_instructions: Optional[List[dict]] = None
    distance_km: float
    estimated_travel_time_minutes: float
    eta_hours: Optional[float] = None
    duration_hours: Optional[float] = None
    duration_formatted: Optional[str] = None
    route_risk: float
    risk_level: Optional[str] = None
    status: Optional[str] = None
    safety_score: float
    alternative_routes_available: int
    alternatives: Optional[List[dict]] = None
    weather_risk: Optional[float] = None
    weather_condition: Optional[str] = None
    rain_probability: Optional[float] = None
    rainfall_mm: Optional[float] = None
    temperature_c: Optional[float] = None
    humidity_pct: Optional[float] = None
    wind_kmh: Optional[float] = None
    aqi: Optional[int] = None
    aqi_category: Optional[str] = None
    pm2_5: Optional[float] = None
    pm10: Optional[float] = None
    uv_index: Optional[float] = None
    uv_category: Optional[str] = None
    is_raining: Optional[bool] = None
    rain_forecast_summary: Optional[str] = None
    rain_hotspots: Optional[List[dict]] = None
    hourly_forecast: Optional[List[dict]] = None
    flood_risk: Optional[float] = None
    flood_summary: Optional[str] = None
    river_discharge: Optional[float] = None
    landslide_risk: Optional[float] = None
    landslide_source: Optional[str] = None
    nrsc_landslide_risk: Optional[float] = None
    imd_warning_risk: Optional[float] = None
    news_risk: Optional[float] = None
    live_incidents: Optional[List[dict]] = None
    disaster_news: Optional[List[dict]] = None
    data_provenance: Optional[dict] = None
    data_sources: Optional[List[str]] = None
    departure_datetime: Optional[str] = None
    estimated_arrival_datetime: Optional[str] = None
    generated_at: str

    @classmethod
    def create(cls, **kwargs: Any) -> RouteResponse:
        kwargs.setdefault(
            "generated_at",
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        dep_d = kwargs.pop("departure_date", None)
        dep_t = kwargs.pop("departure_time", None)
        if dep_d and dep_t:
            kwargs["departure_datetime"] = f"{dep_d} {dep_t}"
        elif not kwargs.get("departure_datetime"):
            kwargs["departure_datetime"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        if "road_ids" in kwargs and "route" not in kwargs:
            kwargs["route"] = kwargs["road_ids"]
        if "estimated_travel_time_minutes" in kwargs:
            mins_total = float(kwargs["estimated_travel_time_minutes"] or 0)
            kwargs["eta_hours"] = round(mins_total / 60.0, 1)
            kwargs["duration_hours"] = kwargs["eta_hours"]
            h = int(mins_total // 60)
            m = int(round(mins_total % 60))
            if m == 60:
                h += 1
                m = 0
            kwargs["duration_formatted"] = f"{h}h {m:02d}m" if h > 0 else f"{m}m"
        elif "duration_hours" in kwargs and kwargs["duration_hours"] is not None:
            mins_total = float(kwargs["duration_hours"]) * 60.0
            kwargs["eta_hours"] = kwargs["duration_hours"]
            h = int(mins_total // 60)
            m = int(round(mins_total % 60))
            kwargs["duration_formatted"] = f"{h}h {m:02d}m" if h > 0 else f"{m}m"

        mins_for_arr = float(kwargs.get("estimated_travel_time_minutes") or 0)
        dep_str = kwargs.get("departure_datetime")
        if dep_str and not kwargs.get("estimated_arrival_datetime"):
            try:
                from datetime import timedelta
                clean_dep = dep_str.replace(" UTC", "").replace("T", " ")
                dep_dt = datetime.strptime(clean_dep[:16], "%Y-%m-%d %H:%M")
                arr_dt = dep_dt + timedelta(minutes=mins_for_arr)
                kwargs["estimated_arrival_datetime"] = arr_dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                pass

        risk_val = float(kwargs.get("route_risk", 0.15) or 0.15)
        if "risk_level" not in kwargs or kwargs["risk_level"] is None:
            kwargs["risk_level"] = "CRITICAL" if risk_val > 0.40 else "HIGH" if risk_val > 0.25 else "MODERATE" if risk_val > 0.15 else "LOW"
        if "status" not in kwargs or kwargs["status"] is None:
            kwargs["status"] = "RESTRICTED" if risk_val > 0.35 else "CAUTION" if risk_val > 0.20 else "OPTIMAL"

        return cls(**kwargs)

