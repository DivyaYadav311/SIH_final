"""Live feature collection for the landslide agent.

Sources:
- Open-Meteo forecast API: current/hourly weather and precipitation.
- Open-Meteo Elevation API: Copernicus GLO-90 elevation.
- NASA COOLR ArcGIS FeatureServer: nearby historical landslide events.
- OpenStreetMap Overpass: nearby land-use/natural-land-cover tags.

No API key is required for the non-commercial/demo endpoints used here.
"""

from __future__ import annotations

import math
import os
from datetime import datetime, timezone
from typing import Any

import requests

OPEN_METEO_FORECAST = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_ELEVATION = "https://api.open-meteo.com/v1/elevation"
NASA_COOLR = os.environ.get(
    "NASA_COOLR_URL",
    "https://gis.earthdata.nasa.gov/gis05/rest/services/"
    "Landslides/COOLR_Events_Points/FeatureServer/0/query",
)
OVERPASS = "https://overpass-api.de/api/interpreter"
TIMEOUT = 15
HTTP_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "landslide-agent-demo/2.0 (contact: maintainer@example.invalid)",
}

LAND_COVER_MAP = {
    "forest": "forest",
    "wood": "forest",
    "farmland": "cropland",
    "farmyard": "cropland",
    "orchard": "cropland",
    "vineyard": "cropland",
    "grass": "grassland",
    "meadow": "grassland",
    "scrub": "shrubland",
    "heath": "shrubland",
    "wetland": "wetland",
    "residential": "urban",
    "commercial": "urban",
    "industrial": "urban",
    "retail": "urban",
    "construction": "urban",
    "quarry": "barren",
    "bare_rock": "barren",
    "scree": "barren",
    "sand": "barren",
    "beach": "barren",
    "glacier": "snow_ice",
    "ice_shelf": "snow_ice",
}


def _get(url: str, params: dict[str, Any]) -> dict[str, Any]:
    response = requests.get(url, params=params, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


def _hourly_value(values: list[Any], index: int) -> float:
    value = values[index]
    return float(value or 0.0)


def fetch_weather(latitude: float, longitude: float) -> dict[str, float]:
    """Fetch current conditions and recent hourly precipitation from Open-Meteo."""
    data = _get(
        OPEN_METEO_FORECAST,
        {
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,relative_humidity_2m,precipitation",
            "hourly": "precipitation",
            "past_hours": 168,
            "forecast_hours": 1,
            "timezone": "UTC",
            "precipitation_unit": "mm",
        },
    )

    current = data.get("current", {})
    hourly = data.get("hourly", {})
    precip = [float(x or 0.0) for x in hourly.get("precipitation", [])]

    # The final hourly entries are the most recent hours returned by the API.
    # Use the latest 1/6/24/168 hours for accumulated rainfall.
    rainfall_1h = sum(precip[-1:])
    rainfall_6h = sum(precip[-6:])
    rainfall_24h = sum(precip[-24:])
    rainfall_7d = sum(precip[-168:])

    return {
        "rainfall_1h_mm": rainfall_1h,
        "rainfall_6h_mm": rainfall_6h,
        "rainfall_24h_mm": rainfall_24h,
        "rainfall_7d_mm": rainfall_7d,
        "temperature_c": float(current.get("temperature_2m", 0.0)),
        "humidity_percent": float(current.get("relative_humidity_2m", 0.0)),
    }


def fetch_elevation_grid(latitude: float, longitude: float) -> list[float]:
    """Fetch a 3x3 DEM neighbourhood and return values row-major."""
    lat_step = 0.001  # about 111 m
    lon_step = 0.001 / max(math.cos(math.radians(latitude)), 0.2)
    coords = [
        (latitude + dy * lat_step, longitude + dx * lon_step)
        for dy in (-1, 0, 1)
        for dx in (-1, 0, 1)
    ]
    data = _get(
        OPEN_METEO_ELEVATION,
        {
            "latitude": ",".join(str(p[0]) for p in coords),
            "longitude": ",".join(str(p[1]) for p in coords),
        },
    )
    elevations = data.get("elevation")
    if not elevations or len(elevations) != 9:
        raise RuntimeError("Elevation API did not return a 3x3 terrain grid")
    return [float(x) for x in elevations]


def derive_slope_aspect(grid: list[float], latitude: float) -> tuple[float, float, float]:
    """Derive slope/aspect from a 3x3 DEM using the Horn method."""
    z = [grid[i:i + 3] for i in range(0, 9, 3)]
    cell_y = 111_320.0 * 0.001
    cell_x = 111_320.0 * math.cos(math.radians(latitude)) * 0.001

    dzdx = (
        (z[0][2] + 2 * z[1][2] + z[2][2])
        - (z[0][0] + 2 * z[1][0] + z[2][0])
    ) / (8 * cell_x)
    dzdy = (
        (z[2][0] + 2 * z[2][1] + z[2][2])
        - (z[0][0] + 2 * z[0][1] + z[0][2])
    ) / (8 * cell_y)

    slope = math.degrees(math.atan(math.sqrt(dzdx * dzdx + dzdy * dzdy)))
    aspect = math.degrees(math.atan2(dzdx, -dzdy))
    if aspect < 0:
        aspect += 360.0
    if slope < 0.05:
        aspect = 0.0

    return float(z[1][1]), round(slope, 2), round(aspect, 2)


def fetch_historical_landslide_count(
    latitude: float,
    longitude: float,
    radius_km: float = 25.0
) -> int:
    """Count nearby historical landslides from NASA COOLR.

    NASA COOLR is an external service, so failure of this optional
    feature should not stop the entire live prediction pipeline.
    """

    params = {
        "where": "1=1",
        "geometry": f"{longitude},{latitude}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "distance": radius_km,
        "units": "esriSRUnit_Kilometer",
        "returnCountOnly": "true",
        "f": "json",
    }

    try:
        data = _get(NASA_COOLR, params)
        count = data.get("count")
        if count is None:
            raise ValueError("NASA COOLR response did not contain count")
        return max(0, int(count))
    except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
        print(f"WARNING: NASA COOLR unavailable: {exc}")
        return 0


def _fetch_historical_landslide_count_live(
    latitude: float, longitude: float, radius_km: float = 25.0
) -> int:
    """Fetch NASA history without converting an upstream failure to zero."""
    params = {
        "where": "1=1",
        "geometry": f"{longitude},{latitude}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "distance": radius_km,
        "units": "esriSRUnit_Kilometer",
        "returnCountOnly": "true",
        "f": "json",
    }
    data = _get(NASA_COOLR, params)
    count = data.get("count")
    if count is None:
        raise ValueError("NASA COOLR response did not contain count")
    return max(0, int(count))


def _land_cover_from_tags(tags: dict[str, Any]) -> str | None:
    for key in ("landuse", "natural"):
        value = tags.get(key)
        if value in LAND_COVER_MAP:
            return LAND_COVER_MAP[value]
    return None


def fetch_land_cover(latitude: float, longitude: float, radius_m: int = 500) -> str:
    """Find the nearest useful OSM land-use/natural feature."""
    try:
        return _fetch_land_cover_live(latitude, longitude, radius_m)
    except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
        print(f"WARNING: OpenStreetMap unavailable: {exc}")
        return "grassland"


def _fetch_land_cover_live(latitude: float, longitude: float, radius_m: int = 500) -> str:
    """Fetch and map the nearest useful OSM feature without fallback."""
    query = f"""
    [out:json][timeout:10];
    nwr(around:{radius_m},{latitude},{longitude})[landuse];
    out tags center;
    nwr(around:{radius_m},{latitude},{longitude})[natural];
    out tags center;
    """
    response = requests.post(
        OVERPASS, data=query, headers=HTTP_HEADERS, timeout=TIMEOUT
    )
    response.raise_for_status()
    elements = response.json().get("elements", [])
    if not isinstance(elements, list):
        raise ValueError("OpenStreetMap response did not contain elements")
    # OSM does not provide a complete land-cover raster; this is contextual.
    for element in elements:
        mapped = _land_cover_from_tags(element.get("tags", {}))
        if mapped:
            return mapped
    raise ValueError("OpenStreetMap returned no mapped land-use feature")


def collect_live_features(latitude: float, longitude: float) -> dict[str, Any]:
    source_status = {}
    try:
        weather = fetch_weather(latitude, longitude)
        source_status["weather"] = "live"
    except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
        print(f"WARNING: Open-Meteo weather unavailable: {exc}")
        weather = {
            "rainfall_1h_mm": 0.0, "rainfall_6h_mm": 0.0,
            "rainfall_24h_mm": 0.0, "rainfall_7d_mm": 0.0,
            "temperature_c": 0.0, "humidity_percent": 0.0,
        }
        source_status["weather"] = "fallback"

    try:
        grid = fetch_elevation_grid(latitude, longitude)
        elevation, slope, aspect = derive_slope_aspect(grid, latitude)
        source_status["elevation"] = "live"
        source_status["terrain_derivatives"] = "calculated_from_live_elevation"
    except (requests.RequestException, ValueError, TypeError, KeyError, RuntimeError) as exc:
        print(f"WARNING: Open-Meteo elevation unavailable: {exc}")
        elevation, slope, aspect = 0.0, 0.0, 0.0
        source_status["elevation"] = "fallback"
        source_status["terrain_derivatives"] = "fallback"

    try:
        history = _fetch_historical_landslide_count_live(latitude, longitude)
        source_status["historical_landslides"] = "live"
    except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
        print(f"WARNING: NASA COOLR unavailable: {exc}")
        history = 0
        source_status["historical_landslides"] = "fallback"

    try:
        land_cover = _fetch_land_cover_live(latitude, longitude)
        source_status["land_cover"] = "live"
    except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
        print(f"WARNING: OpenStreetMap unavailable: {exc}")
        land_cover = "grassland"
        source_status["land_cover"] = "fallback"

    return {
        # Coordinates are internal model features.  Response schemas ignore
        # these extra keys, so the public API contract remains unchanged.
        "latitude": float(latitude),
        "longitude": float(longitude),
        **weather,
        "elevation_m": round(elevation, 2),
        "slope_degree": slope,
        "aspect_degree": aspect,
        "land_cover": land_cover,
        "historical_landslide_count": history,
        "source_status": source_status,
    }


def data_sources() -> dict[str, str]:
    return {
        "weather": "Open-Meteo Forecast API",
        "elevation": "Open-Meteo Elevation API / Copernicus GLO-90",
        "historical_landslides": "NASA COOLR Events FeatureServer",
        "land_cover": "OpenStreetMap Overpass API",
        "terrain_derivatives": "Slope/aspect calculated from live DEM",
    }
