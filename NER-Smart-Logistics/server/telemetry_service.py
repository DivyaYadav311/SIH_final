"""
NER Smart Logistics — Live Vehicle Telemetry & Fleet Tracking Service
=====================================================================
Handles real-time GPS tracking for active relief convoys and logistics vehicles:
- Ingests live GPS pings from driver mobile devices or vehicle IoT units
- Maintains current vehicle positions, speeds, headings, and breadcrumb trails
- Evaluates proactive hazard proximity geofencing (P1/P2/P3 hazards)
- Broadcasts real-time vehicle updates via WebSocket to Control Tower dashboards
"""
from __future__ import annotations

import asyncio
import math
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse

# ---------------------------------------------------------------------------
# DATA SCHEMAS
# ---------------------------------------------------------------------------
class GPSPing(BaseModel):
    vehicle_id: str = Field(..., description="Unique vehicle ID e.g. TRK_AS01_4210")
    driver_name: str = Field(default="Driver", description="Driver's name")
    shipment_id: Optional[str] = Field(default=None, description="Linked shipment ID")
    latitude: float = Field(..., ge=-90.0, le=90.0, description="WGS84 latitude")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="WGS84 longitude")
    speed_kmh: float = Field(default=0.0, ge=0.0, description="Vehicle speed in km/h")
    heading: float = Field(default=0.0, ge=0.0, le=360.0, description="Compass heading 0-360 deg")
    accuracy_m: Optional[float] = Field(default=10.0, description="GPS accuracy in meters")
    origin: Optional[str] = Field(default=None, description="Trip origin")
    destination: Optional[str] = Field(default=None, description="Trip destination")
    status: str = Field(default="EN_ROUTE", description="Vehicle status: EN_ROUTE, IDLE, DELIVERED, DISTRESS")
    cargo_type: Optional[str] = Field(default="RELIEF_SUPPLIES", description="Type of cargo")
    mode: str = Field(default="live_gps", description="Tracking mode: live_gps or demo_simulation")


class VehicleState(BaseModel):
    vehicle_id: str
    driver_name: str
    shipment_id: Optional[str] = None
    latitude: float
    longitude: float
    speed_kmh: float
    heading: float
    accuracy_m: float = 10.0
    origin: Optional[str] = None
    destination: Optional[str] = None
    status: str = "EN_ROUTE"
    cargo_type: str = "RELIEF_SUPPLIES"
    mode: str = "live_gps"
    last_ping_ts: float
    last_ping_iso: str
    distance_traveled_km: float = 0.0
    active_alerts: List[Dict[str, Any]] = []


# ---------------------------------------------------------------------------
# HAVERSINE DISTANCE HELPER
# ---------------------------------------------------------------------------
def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(min(1.0, a)))


# ---------------------------------------------------------------------------
# TELEMETRY MANAGER (Thread-safe in-memory store)
# ---------------------------------------------------------------------------
class TelemetryManager:
    def __init__(self):
        self._vehicles: Dict[str, VehicleState] = {}
        self._trails: Dict[str, List[Dict[str, Any]]] = {}  # vehicle_id -> list of [lat, lng, ts, speed]
        self._max_trail_points = 200
        self._listeners: Set[WebSocket] = set()

        # Known regional critical hazard checkpoints for proximity geofencing
        self._hazard_zones: List[Dict[str, Any]] = [
            {"id": "HZ_01", "name": "Brahmaputra Flood Plain (Morigaon)", "lat": 26.25, "lon": 92.34, "hazard": "FLOOD", "radius_km": 15.0},
            {"id": "HZ_02", "name": "Sela Pass Landslide Corridor (Tawang)", "lat": 27.50, "lon": 92.10, "hazard": "LANDSLIDE", "radius_km": 12.0},
            {"id": "HZ_03", "name": "NH-29 Landslide Chokepoint (Kohima)", "lat": 25.67, "lon": 94.10, "hazard": "LANDSLIDE", "radius_km": 10.0},
            {"id": "HZ_04", "name": "NH-6 Sonapur Tunnel Inundation (Meghalaya)", "lat": 25.10, "lon": 92.36, "hazard": "ROAD_BLOCKED", "radius_km": 8.0},
            {"id": "HZ_05", "name": "Loktak Lake Inundation (Manipur)", "lat": 24.55, "lon": 93.80, "hazard": "FLOOD", "radius_km": 15.0},
        ]

    def register_listener(self, ws: WebSocket):
        self._listeners.add(ws)

    def remove_listener(self, ws: WebSocket):
        self._listeners.discard(ws)

    def check_hazard_proximity(self, lat: float, lon: float) -> List[Dict[str, Any]]:
        alerts = []
        for zone in self._hazard_zones:
            dist = haversine_km(lat, lon, zone["lat"], zone["lon"])
            if dist <= zone["radius_km"]:
                alerts.append({
                    "hazard_id": zone["id"],
                    "hazard_name": zone["name"],
                    "hazard_type": zone["hazard"],
                    "distance_km": round(dist, 2),
                    "warning": f"Approaching {zone['hazard']} zone ({round(dist, 1)} km away)",
                    "severity": "CRITICAL" if dist < 5.0 else "WARNING",
                })
        return alerts

    async def record_ping(self, ping: GPSPing) -> VehicleState:
        now = time.time()
        iso_now = datetime.now(timezone.utc).isoformat()
        vid = ping.vehicle_id

        # Calculate incremental distance
        distance_inc = 0.0
        if vid in self._vehicles:
            prev = self._vehicles[vid]
            distance_inc = haversine_km(prev.latitude, prev.longitude, ping.latitude, ping.longitude)
            # Filter noise jumps > 100km in 1 ping
            if distance_inc > 100.0:
                distance_inc = 0.0
            total_dist = prev.distance_traveled_km + distance_inc
        else:
            total_dist = 0.0

        # Check proximity to known hazards
        alerts = self.check_hazard_proximity(ping.latitude, ping.longitude)

        # Update or create vehicle state
        state = VehicleState(
            vehicle_id=vid,
            driver_name=ping.driver_name,
            shipment_id=ping.shipment_id,
            latitude=ping.latitude,
            longitude=ping.longitude,
            speed_kmh=ping.speed_kmh,
            heading=ping.heading,
            accuracy_m=ping.accuracy_m or 10.0,
            origin=ping.origin,
            destination=ping.destination,
            status=ping.status,
            cargo_type=ping.cargo_type or "RELIEF_SUPPLIES",
            mode=ping.mode,
            last_ping_ts=now,
            last_ping_iso=iso_now,
            distance_traveled_km=round(total_dist, 2),
            active_alerts=alerts,
        )
        self._vehicles[vid] = state

        # Record trail
        if vid not in self._trails:
            self._trails[vid] = []
        trail = self._trails[vid]
        trail.append({
            "lat": ping.latitude,
            "lng": ping.longitude,
            "ts": now,
            "speed": ping.speed_kmh,
        })
        if len(trail) > self._max_trail_points:
            trail.pop(0)

        # Broadcast update asynchronously
        asyncio.create_task(self._broadcast_update(state))
        return state

    async def _broadcast_update(self, state: VehicleState):
        if not self._listeners:
            return
        payload = {
            "type": "vehicle_telemetry_ping",
            "vehicle": state.model_dump(),
            "timestamp": time.time(),
        }
        dead_listeners = []
        for ws in list(self._listeners):
            try:
                await ws.send_json(payload)
            except Exception:
                dead_listeners.append(ws)
        for ws in dead_listeners:
            self.remove_listener(ws)

    def get_all_vehicles(self) -> List[VehicleState]:
        # Return all active vehicles; mark offline if no ping in > 10 mins
        now = time.time()
        result = []
        for state in self._vehicles.values():
            if now - state.last_ping_ts > 600:
                copy = state.model_copy()
                copy.status = "OFFLINE"
                result.append(copy)
            else:
                result.append(state)
        return result

    def get_vehicle(self, vehicle_id: str) -> Optional[VehicleState]:
        return self._vehicles.get(vehicle_id)

    def get_trail(self, vehicle_id: str) -> List[Dict[str, Any]]:
        return self._trails.get(vehicle_id, [])


# Singleton Telemetry Manager
telemetry_manager = TelemetryManager()

# ---------------------------------------------------------------------------
# FASTAPI ROUTER
# ---------------------------------------------------------------------------
router = APIRouter(prefix="/api/v1/telemetry", tags=["telemetry"])

@router.post("/ping", response_model=VehicleState)
async def api_telemetry_ping(ping: GPSPing):
    """Receive real-time GPS telemetry from driver mobile app or simulation."""
    try:
        return await telemetry_manager.record_ping(ping)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to record telemetry: {exc}")


@router.get("/vehicles")
async def api_get_active_vehicles():
    """List all currently tracked vehicles and their latest GPS positions."""
    vehicles = telemetry_manager.get_all_vehicles()
    return {
        "count": len(vehicles),
        "vehicles": [v.model_dump() for v in vehicles],
        "server_time": time.time(),
    }


@router.get("/vehicles/{vehicle_id}")
async def api_get_vehicle(vehicle_id: str):
    """Fetch live telemetry for a specific vehicle."""
    v = telemetry_manager.get_vehicle(vehicle_id)
    if not v:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return v.model_dump()


@router.get("/vehicles/{vehicle_id}/trail")
async def api_get_vehicle_trail(vehicle_id: str):
    """Fetch breadcrumb coordinates for a vehicle's traveled path."""
    trail = telemetry_manager.get_trail(vehicle_id)
    return {
        "vehicle_id": vehicle_id,
        "point_count": len(trail),
        "trail": trail,
    }
