"""Configuration for the real-network, disaster-aware routing engine."""
from __future__ import annotations
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_UNIFIED_CACHE = os.path.join(os.path.dirname(BASE_DIR), "data", "p4_routing", "graph_cache")
_LOCAL_CACHE = os.path.join(BASE_DIR, "data", "graph_cache")
GRAPH_CACHE_DIR = _UNIFIED_CACHE if os.path.exists(_UNIFIED_CACHE) else _LOCAL_CACHE

ROUTE_CORRIDOR_BUFFER_KM = float(os.getenv("ROUTE_CORRIDOR_BUFFER_KM", "80"))
ROUTE_MAX_DOWNLOAD_AREA_KM2 = float(os.getenv("ROUTE_MAX_DOWNLOAD_AREA_KM2", "450000"))
MAX_SNAP_DISTANCE_KM = float(os.getenv("MAX_SNAP_DISTANCE_KM", "80"))

# OSM/Overpass: smaller corridor tiles are important for long Northeast routes.
OSM_TILE_LENGTH_KM = float(os.getenv("OSM_TILE_LENGTH_KM", "70"))
OSM_TILE_BUFFER_KM = float(os.getenv("OSM_TILE_BUFFER_KM", "35"))
OVERPASS_TIMEOUT_SECONDS = int(os.getenv("OVERPASS_TIMEOUT_SECONDS", "30"))
OVERPASS_ENDPOINTS = [
    x.strip() for x in os.getenv(
        "OVERPASS_ENDPOINTS",
        "https://overpass-api.de/api,"
        "https://overpass.kumi.systems/api",
    ).split(",") if x.strip()
]

# Real-road fallback when all Overpass instances are unavailable.
# This does NOT create straight-line/fake roads: OSRM returns a route over
# mapped drivable road infrastructure.
OSRM_ROUTING_URL = os.getenv(
    "OSRM_ROUTING_URL",
    "https://router.project-osrm.org/route/v1/driving",
)
OSRM_TIMEOUT_SECONDS = int(os.getenv("OSRM_TIMEOUT_SECONDS", "20"))
OSRM_ALTERNATIVES = int(os.getenv("OSRM_ALTERNATIVES", "3"))

WEATHER_API_URL = "https://api.open-meteo.com/v1/forecast"
FLOOD_API_URL = "https://flood-api.open-meteo.com/v1/flood"

WEIGHT_TRAVEL_TIME = 1.0
WEIGHT_DISTANCE = 0.25
WEIGHT_RISK = 140.0
TRANSFER_PENALTY_MIN = 25.0

PRIORITY_RISK_MULTIPLIER = {
    "critical": 5.0,
    "high": 3.0,
    "medium": 1.5,
    "low": 1.0,
}

ROAD_SPEED_KMH = {
    "motorway": 90, "motorway_link": 60,
    "trunk": 70, "trunk_link": 55,
    "primary": 55, "primary_link": 45,
    "secondary": 40, "secondary_link": 35,
    "tertiary": 30, "tertiary_link": 25,
    "residential": 25, "unclassified": 20,
    "service": 15, "living_street": 10,
    "track": 12, "road": 30,
}
DEFAULT_SPEED_KMH = 25

RISK_GRID_STEP_DEG = float(os.getenv("RISK_GRID_STEP_DEG", "0.5"))
RISK_CACHE_TTL_SECONDS = 900
RISK_REQUEST_BATCH = 100
HIGH_RISK_THRESHOLD = 0.70
MAX_ALTERNATIVE_ROUTES = 3
NEWS_RISK_WEIGHT = 1.0
NEWS_CACHE_TTL_SECONDS = 900
ALLOW_RISK_API_FALLBACK = True