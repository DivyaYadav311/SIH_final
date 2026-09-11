"""Environmental and incident risk enrichment for travelable routes.

Weather/flood values come from live model APIs. IMD warnings come from the
public IMD CAP stream. NRSC/ISRO landslide scoring is used only when a real
NRSC GeoJSON export is configured; otherwise a clearly labelled terrain/rain
susceptibility proxy is used and never presented as an NRSC observation.
"""
from __future__ import annotations

import logging
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import httpx

from p4_src.config import (
    FLOOD_API_URL,
    RISK_CACHE_TTL_SECONDS,
    RISK_GRID_STEP_DEG,
    RISK_REQUEST_BATCH,
    WEATHER_API_URL,
)
from p4_src.official_data import (
    fetch_imd_cap_alerts,
    imd_warning_risk_for_point,
    load_nrsc_geojson,
)
from p4_src.news_intelligence import news_risk_for_point

logger = logging.getLogger(__name__)

_cache = {}
_cache_timestamp = 0.0
_cache_bbox = None
_nrsc_geojson = None


def _weather_condition(code) -> str:
    try:
        code = int(code)
    except Exception:
        return "Unknown"
    mapping = {
        0: "Clear sky",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Fog",
        48: "Depositing rime fog",
        51: "Light drizzle",
        53: "Moderate drizzle",
        55: "Dense drizzle",
        56: "Freezing drizzle",
        57: "Dense freezing drizzle",
        61: "Light rain",
        63: "Moderate rain",
        65: "Heavy rain",
        66: "Freezing rain",
        67: "Heavy freezing rain",
        71: "Light snow",
        73: "Moderate snow",
        75: "Heavy snow",
        77: "Snow grains",
        80: "Light rain showers",
        81: "Moderate rain showers",
        82: "Violent rain showers",
        85: "Light snow showers",
        86: "Heavy snow showers",
        95: "Thunderstorm",
        96: "Thunderstorm with hail",
        99: "Thunderstorm with heavy hail",
    }
    return mapping.get(code, "Unknown")


def _weather_risk(w: dict) -> float:
    if not w:
        return 0.15
    risk = 0.03
    precip = float(w.get("precipitation", 0) or 0)
    rain = float(w.get("rain", 0) or 0)
    showers = float(w.get("showers", 0) or 0)
    snow = float(w.get("snowfall", 0) or 0)
    wind = max(
        float(w.get("wind_speed_10m", 0) or 0),
        float(w.get("wind_gusts_10m", 0) or 0),
    )
    probability = float(w.get("precipitation_probability", 0) or 0)
    code = int(w.get("weather_code", 0) or 0)

    if max(precip, rain, showers) > 20:
        risk += 0.40
    elif max(precip, rain, showers) > 10:
        risk += 0.25
    elif max(precip, rain, showers) > 5:
        risk += 0.15
    elif max(precip, rain, showers) > 1:
        risk += 0.05

    risk += min(probability / 100.0, 1.0) * 0.08

    if snow > 5:
        risk += 0.25
    elif snow > 1:
        risk += 0.12

    if wind > 80:
        risk += 0.25
    elif wind > 50:
        risk += 0.15
    elif wind > 30:
        risk += 0.05

    if code >= 95:
        risk += 0.25
    elif code >= 80:
        risk += 0.12
    elif code >= 61:
        risk += 0.08

    return min(risk, 1.0)


def _flood_risk(f: dict, w: dict | None = None) -> float:
    """Calculate compound flood & pluvial waterlogging risk combining river discharge,
    precipitation rate, atmospheric/soil saturation (humidity), and squall winds.
    """
    discharge = float(f.get("river_discharge", 0) or 0)
    base_discharge_risk = 0.05
    if discharge > 1000:
        base_discharge_risk = 0.90
    elif discharge > 500:
        base_discharge_risk = 0.70
    elif discharge > 200:
        base_discharge_risk = 0.50
    elif discharge > 100:
        base_discharge_risk = 0.30
    elif discharge > 50:
        base_discharge_risk = 0.15

    if not w:
        return base_discharge_risk

    rain = float(w.get("precipitation", 0) or w.get("rain", 0) or 0)
    rain_prob = float(w.get("precipitation_probability", 0) or 0)
    humidity = float(w.get("relative_humidity_2m", 60) or 60)
    wind = float(w.get("wind_speed_10m", 10) or 10)

    # Pluvial surface runoff & flash waterlogging risk:
    pluvial_risk = 0.0
    if rain > 35.0:  # Torrential downpour / cloudburst
        pluvial_risk += 0.60
    elif rain > 20.0:  # Heavy monsoon rain
        pluvial_risk += 0.45
    elif rain > 10.0:  # Moderate rain
        pluvial_risk += 0.30
    elif rain > 3.0:  # Light to moderate showers
        pluvial_risk += 0.15
    elif rain > 0.5:  # Drizzle
        pluvial_risk += 0.06

    # Precipitation probability scaling
    if rain_prob > 80:
        pluvial_risk += 0.10
    elif rain_prob > 50:
        pluvial_risk += 0.05

    # High humidity (>80%) means saturated soil and air, severely reducing drainage
    if humidity > 90 and (rain > 0.5 or rain_prob > 50):
        pluvial_risk += 0.12
    elif humidity > 80 and (rain > 0.5 or rain_prob > 40):
        pluvial_risk += 0.06

    # High winds (>35 km/h) with rain produce storm surges, waves on standing water, and blow debris into culverts
    if wind > 60 and rain > 2.0:
        pluvial_risk += 0.15
    elif wind > 35 and rain > 1.0:
        pluvial_risk += 0.08

    total_flood_risk = max(base_discharge_risk, pluvial_risk)
    # Compound effect: if river discharge is elevated AND intense surface rain occurs simultaneously
    if base_discharge_risk >= 0.30 and pluvial_risk >= 0.20:
        total_flood_risk = min(1.0, total_flood_risk + 0.15)

    return round(min(total_flood_risk, 1.0), 3)


def _flood_summary(f: dict, w: dict | None = None) -> str:
    """Generate human-readable flood and waterlogging assessment."""
    risk = _flood_risk(f, w)
    rain = float((w or {}).get("precipitation", 0) or (w or {}).get("rain", 0) or 0)
    rain_prob = float((w or {}).get("precipitation_probability", 0) or 0)
    humidity = float((w or {}).get("relative_humidity_2m", 60) or 60)
    wind = float((w or {}).get("wind_speed_10m", 10) or 10)
    discharge = float((f or {}).get("river_discharge", 0) or 0)

    factors = []
    if discharge > 100:
        factors.append(f"high river discharge ({discharge:.0f} m³/s)")
    if rain > 10:
        factors.append(f"heavy rainfall ({rain:.1f} mm)")
    elif rain > 1:
        factors.append(f"active rain ({rain:.1f} mm, {rain_prob:.0f}% prob)")
    if humidity > 85:
        factors.append(f"high humidity/saturation ({humidity:.0f}%)")
    if wind > 40:
        factors.append(f"squall winds ({wind:.0f} km/h)")

    if risk >= 0.65:
        return f"CRITICAL FLOOD ALERT: High waterlogging & riverine inundation risk. Exacerbated by {', '.join(factors) if factors else 'intense weather'}."
    if risk >= 0.35:
        return f"MODERATE INUNDATION RISK: Waterlogging expected in low-lying underpasses and catchment corridors ({', '.join(factors) if factors else 'elevated moisture'})."
    if risk >= 0.18:
        return f"MINOR SURFACE RUNOFF: Light surface ponding possible ({humidity:.0f}% humidity, {wind:.0f} km/h winds)."
    return f"NOMINAL DRAINAGE: Low flood risk ({humidity:.0f}% humidity, {wind:.0f} km/h wind). Clear transit conditions."



def _terrain_landslide_risk(lat: float, lon: float, weather: dict) -> float:
    """Relative susceptibility proxy, never an active-landslide probability.

    This is used only when no NRSC vector dataset is configured. It combines
    broad hill-belt geography with forecast precipitation and is explicitly
    labelled as a modelled proxy in the API response.
    """
    # Comprehensive hill belt detection covering Himalayas, Northeast Hills, Western Ghats,
    # Eastern Ghats, Vindhya/Satpura, Nilgiris, and global elevated terrain corridors
    hill_belt = (
        (20.0 <= lat <= 37.0 and 70.0 <= lon <= 98.0)  # Himalayan & Northeast Mountain Systems
        or (8.0 <= lat <= 21.0 and 72.5 <= lon <= 78.0)  # Western Ghats & Nilgiri Hills
        or (11.0 <= lat <= 22.0 and 77.0 <= lon <= 85.5)  # Eastern Ghats
        or (21.0 <= lat <= 25.5 and 73.0 <= lon <= 83.5)  # Central Indian Highlands
    )
    base = 0.22 if hill_belt else 0.04
    rain = float(weather.get("precipitation", 0) or weather.get("rain", 0) or 0)
    if rain > 25:
        base *= 2.2
    elif rain > 10:
        base *= 1.6
    elif rain > 3:
        base *= 1.25
    if float(weather.get("snowfall", 0) or 0) > 2:
        base += 0.15
    return min(base, 1.0)


def _bbox_grid(bbox, max_points=20):
    north, south, east, west = bbox
    points = []
    lat = south
    while lat <= north + 1e-9:
        lon = west
        while lon <= east + 1e-9:
            points.append((round(lat, 3), round(lon, 3)))
            lon += RISK_GRID_STEP_DEG
        lat += RISK_GRID_STEP_DEG
    if len(points) > max_points:
        stride = math.ceil(len(points) / max_points)
        points = points[::stride][:max_points]
    return points


def _nearest_hour_index(times, target):
    if not times:
        return 0
    try:
        target_dt = datetime.fromisoformat(str(target).replace("Z", "+00:00"))
        best = min(
            range(len(times)),
            key=lambda i: abs(
                datetime.fromisoformat(str(times[i]).replace("Z", "+00:00"))
                - target_dt
            ),
        )
        return best
    except Exception:
        return 0


def _aqi_category(aqi: int | float | None) -> str:
    if aqi is None:
        return "Good"
    val = int(aqi)
    if val <= 50:
        return "Good"
    if val <= 100:
        return "Moderate"
    if val <= 150:
        return "Unhealthy for Sensitive Groups"
    if val <= 200:
        return "Unhealthy"
    if val <= 300:
        return "Very Unhealthy"
    return "Hazardous"


def _uv_category(uv: float | None) -> str:
    if uv is None:
        return "Low"
    val = float(uv)
    if val < 3.0:
        return "Low"
    if val < 6.0:
        return "Moderate"
    if val < 8.0:
        return "High"
    if val < 11.0:
        return "Very High"
    return "Extreme"


def _is_raining(w: dict) -> bool:
    if not w:
        return False
    precip = float(w.get("precipitation", 0) or w.get("rain", 0) or w.get("showers", 0) or 0)
    code = int(w.get("weather_code", 0) or 0)
    rain_codes = {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 99}
    return precip > 0.05 or code in rain_codes


def _batch_weather(points):
    out = {}
    for i in range(0, len(points), RISK_REQUEST_BATCH):
        batch = points[i:i + RISK_REQUEST_BATCH]
        params = {
            "latitude": ",".join(str(p[0]) for p in batch),
            "longitude": ",".join(str(p[1]) for p in batch),
            "current": "precipitation,rain,showers,snowfall,weather_code,wind_speed_10m,wind_gusts_10m,temperature_2m,relative_humidity_2m",
            "hourly": "temperature_2m,precipitation_probability,uv_index,weather_code",
            "forecast_days": 1,
            "timezone": "UTC",
        }
        try:
            with httpx.Client(timeout=8.0, follow_redirects=True) as client:
                r = client.get(WEATHER_API_URL, params=params)
                r.raise_for_status()
                data = r.json()
            items = data if isinstance(data, list) else [data]
            for p, item in zip(batch, items):
                current = dict(item.get("current", {}))
                hourly = item.get("hourly", {}) or {}
                idx = _nearest_hour_index(hourly.get("time", []), current.get("time"))
                probs = hourly.get("precipitation_probability", []) or []
                uv_list = hourly.get("uv_index", []) or []
                temps = hourly.get("temperature_2m", []) or []
                codes = hourly.get("weather_code", []) or []
                times = hourly.get("time", []) or []

                if probs:
                    current["precipitation_probability"] = float(probs[min(idx, len(probs) - 1)])
                if uv_list:
                    current["uv_index"] = float(uv_list[min(idx, len(uv_list) - 1)])
                else:
                    current["uv_index"] = 0.0
                current["condition"] = _weather_condition(current.get("weather_code"))
                current["is_raining"] = _is_raining(current)

                # Extract 8 3-hourly slots for 24-hour daily temperature forecast timeline
                hourly_forecast = []
                if times and temps:
                    target_hours = [3, 6, 9, 12, 15, 18, 21, 0]
                    for th in target_hours:
                        best_i = 0
                        min_diff = 99
                        for i_t, t_str in enumerate(times):
                            try:
                                h_val = int(str(t_str).split("T")[1].split(":")[0])
                                diff = abs(h_val - th)
                                if diff < min_diff:
                                    min_diff = diff
                                    best_i = i_t
                            except Exception:
                                pass
                        t_val = round(float(temps[best_i]), 1) if best_i < len(temps) else current.get("temperature_2m", 25.0)
                        p_val = round(float(probs[best_i])) if best_i < len(probs) else 10
                        c_val = int(codes[best_i]) if best_i < len(codes) else current.get("weather_code", 0)
                        is_night = th in (0, 3, 21)
                        icon = "🌙" if is_night else ("🌧️" if c_val >= 61 or p_val > 60 else ("⛅" if c_val in (1,2,3) else "☀️"))
                        hourly_forecast.append({
                            "time": f"{th:02d}:00",
                            "temperature_c": t_val,
                            "precipitation_probability": p_val,
                            "icon": icon
                        })
                current["hourly_forecast"] = hourly_forecast
                out[p] = current
        except Exception as exc:
            logger.warning("Weather batch failed: %s", exc)
    return out


def _batch_flood(points):
    out = {}
    for i in range(0, len(points), RISK_REQUEST_BATCH):
        batch = points[i:i + RISK_REQUEST_BATCH]
        params = {
            "latitude": ",".join(str(p[0]) for p in batch),
            "longitude": ",".join(str(p[1]) for p in batch),
            "daily": "river_discharge",
            "forecast_days": 1,
        }
        try:
            with httpx.Client(timeout=8.0, follow_redirects=True) as client:
                r = client.get(FLOOD_API_URL, params=params)
                r.raise_for_status()
                data = r.json()
            items = data if isinstance(data, list) else [data]
            for p, item in zip(batch, items):
                vals = [
                    x for x in item.get("daily", {}).get("river_discharge", [])
                    if x is not None
                ]
                out[p] = {"river_discharge": max(vals) if vals else 0}
        except Exception as exc:
            logger.warning("Flood batch failed: %s", exc)
    return out


def _batch_air_quality(points):
    """Fetch live Air Quality Index (US AQI, PM2.5, PM10) from Open-Meteo Air Quality API."""
    out = {}
    for i in range(0, len(points), RISK_REQUEST_BATCH):
        batch = points[i:i + RISK_REQUEST_BATCH]
        params = {
            "latitude": ",".join(str(p[0]) for p in batch),
            "longitude": ",".join(str(p[1]) for p in batch),
            "current": "us_aqi,european_aqi,pm2_5,pm10",
        }
        try:
            with httpx.Client(timeout=8.0, follow_redirects=True) as client:
                r = client.get("https://air-quality-api.open-meteo.com/v1/air-quality", params=params)
                r.raise_for_status()
                data = r.json()
            items = data if isinstance(data, list) else [data]
            for p, item in zip(batch, items):
                cur = dict(item.get("current", {}) or {})
                aqi_val = cur.get("us_aqi")
                if aqi_val is None:
                    aqi_val = cur.get("european_aqi", 42)
                out[p] = {
                    "aqi": int(aqi_val or 45),
                    "aqi_category": _aqi_category(aqi_val or 45),
                    "pm2_5": float(cur.get("pm2_5", 14.0) or 14.0),
                    "pm10": float(cur.get("pm10", 18.0) or 18.0),
                }
        except Exception as exc:
            logger.warning("Air Quality batch failed: %s", exc)
    return out


def _fetch_common_external(points):
    """Fetch weather, air quality, flood and IMD concurrently to reduce route latency."""
    weather = {}
    flood = {}
    air_quality = {}
    alerts = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            pool.submit(_batch_weather, points): "weather",
            pool.submit(_batch_flood, points): "flood",
            pool.submit(_batch_air_quality, points): "air_quality",
            pool.submit(fetch_imd_cap_alerts): "imd",
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                value = future.result()
                if name == "weather":
                    weather = value
                elif name == "flood":
                    flood = value
                elif name == "air_quality":
                    air_quality = value
                else:
                    alerts = value
            except Exception as exc:
                logger.warning("%s risk provider failed: %s", name, exc)
    return weather, flood, air_quality, alerts


def fetch_regional_risk(bbox=None, news_events=None):
    global _cache, _cache_timestamp, _cache_bbox, _nrsc_geojson

    if bbox is None:
        raise ValueError("A route bbox is required for dynamic risk sampling")

    if (
        _cache
        and _cache_bbox == bbox
        and time.time() - _cache_timestamp < RISK_CACHE_TTL_SECONDS
    ):
        return _cache

    points = _bbox_grid(bbox)
    logger.info("Fetching live risk for %d corridor grid points", len(points))

    weather, flood, air_quality, imd_alerts = _fetch_common_external(points)

    if news_events is None:
        news_events = []

    if _nrsc_geojson is None:
        _nrsc_geojson = load_nrsc_geojson()

    result = {}
    for p in points:
        lat, lon = p
        w = weather.get(p, {})
        f = flood.get(p, {})
        aq = air_quality.get(p, {})

        wr = _weather_risk(w)
        fr = _flood_risk(f, w)
        flood_desc = _flood_summary(f, w)
        terrain = _terrain_landslide_risk(lat, lon, w)
        imd_risk, imd_alert = imd_warning_risk_for_point(lat, lon, imd_alerts)
        news_risk, matched_news = news_risk_for_point(lat, lon, news_events)

        nrsc_risk = 0.0
        if _nrsc_geojson:
            try:
                from shapely.geometry import Point, shape
                pt = Point(lon, lat)
                for feat in _nrsc_geojson.get("features", []):
                    geom = feat.get("geometry")
                    if not geom:
                        continue
                    if shape(geom).contains(pt):
                        props = feat.get("properties", {})
                        raw = str(
                            props.get(
                                "severity",
                                props.get("hazard", props.get("class", "low")),
                            )
                        ).lower()
                        nrsc_risk = max(
                            nrsc_risk,
                            {
                                "severe": 0.95,
                                "very high": 0.85,
                                "high": 0.70,
                                "moderate": 0.50,
                                "low": 0.20,
                                "very low": 0.08,
                            }.get(raw, 0.35),
                        )
            except Exception as exc:
                logger.warning("NRSC GeoJSON scoring failed: %s", exc)

        landslide = max(terrain, nrsc_risk)
        disruption = round(
            max(wr, fr, landslide, imd_risk, news_risk),
            3,
        )

        uv = w.get("uv_index", 3.0)
        result[p] = {
            "disruption_probability": disruption,
            "accessibility_score": round((1 - disruption) * 100, 1),
            "weather_risk": round(wr, 3),
            "weather_condition": w.get("condition"),
            "rain_probability": w.get("precipitation_probability"),
            "rainfall_mm": w.get("precipitation"),
            "temperature_c": w.get("temperature_2m"),
            "humidity_pct": w.get("relative_humidity_2m"),
            "wind_kmh": w.get("wind_speed_10m"),
            "uv_index": uv,
            "uv_category": _uv_category(uv),
            "aqi": aq.get("aqi", 52),
            "aqi_category": aq.get("aqi_category", "Moderate"),
            "pm2_5": aq.get("pm2_5", 14.5),
            "pm10": aq.get("pm10", 19.0),
            "is_raining": bool(w.get("is_raining", False)),
            "flood_risk": round(fr, 3),
            "flood_summary": flood_desc,
            "river_discharge": f.get("river_discharge"),
            "landslide_risk": round(landslide, 3),
            "nrsc_landslide_risk": round(nrsc_risk, 3),
            "landslide_source": (
                "NRSC/ISRO GeoJSON"
                if _nrsc_geojson
                else "Modelled terrain + precipitation susceptibility proxy"
            ),
            "imd_warning_risk": round(imd_risk, 3),
            "imd_warning": imd_alert.get("headline") if imd_alert else None,
            "news_risk": round(news_risk, 3),
            "live_incidents": matched_news,
            "hourly_forecast": w.get("hourly_forecast", []),
        }

    _cache, _cache_timestamp, _cache_bbox = result, time.time(), bbox
    return result


def get_risk_for_point(lat, lng, risk_grid=None):
    if not risk_grid:
        return {
            "disruption_probability": 0.15,
            "accessibility_score": 85.0,
            "weather_risk": 0.15,
            "flood_risk": 0.05,
            "flood_summary": "Normal hydrological conditions; low flood probability.",
            "landslide_risk": 0.05,
            "news_risk": 0.0,
            "live_incidents": [],
            "aqi": 45,
            "aqi_category": "Good",
            "pm2_5": 12.0,
            "pm10": 16.0,
            "uv_index": 3.0,
            "uv_category": "Moderate",
            "humidity_pct": 70.0,
            "is_raining": False,
            "landslide_source": "Fallback: no live risk provider data",
        }

    best = min(
        risk_grid,
        key=lambda p: (lat - p[0]) ** 2 + (lng - p[1]) ** 2,
    )
    return risk_grid[best]
