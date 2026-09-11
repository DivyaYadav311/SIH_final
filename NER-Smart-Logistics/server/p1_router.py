"""
P1 Flood Intelligence — FastAPI Router
=======================================
Wraps the existing flood_score.py logic into API endpoints.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("p1-flood")

# ---------------------------------------------------------------------------
# Locate P1 data directory
# ---------------------------------------------------------------------------
P1_ROOT = Path(__file__).resolve().parent.parent / "p1-flood"
P1_DATA_DIR = P1_ROOT / "data"
P1_SRC_DIR = P1_ROOT / "src"

IST = timezone(timedelta(hours=5, minutes=30))

# ---------------------------------------------------------------------------
# Import P1 scoring logic
# ---------------------------------------------------------------------------
import sys
if str(P1_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(P1_SRC_DIR))

try:
    from flood_score import compute_flood_probability, WEIGHT_RAINFALL, WEIGHT_RIVER, WEIGHT_ELEVATION
    P1_SCORING_AVAILABLE = True
except ImportError as e:
    logger.warning("P1 flood_score.py import failed: %s", e)
    P1_SCORING_AVAILABLE = False


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class FloodPredictionRequest(BaseModel):
    """Only lat/lon required. Other params are optional overrides."""
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    segment_id: Optional[str] = None
    rainfall_7day_mm: Optional[float] = None
    elevation_m: Optional[float] = None
    river_proximity_km: Optional[float] = None


class FloodPredictionResponse(BaseModel):
    segment_id: str
    date: str
    flood_probability: float
    confidence: float
    risk_level: str
    contributing_factors: dict
    source_timestamp: str
    coordinates: list[float]
    module: str = "P1_FLOOD"


# ---------------------------------------------------------------------------
# Inline flood computation (in case flood_score import fails)
# ---------------------------------------------------------------------------
def _compute_flood_fallback(rainfall_7day_mm: float, elevation_m: float | None, river_proximity_km: float | None) -> float:
    """Fallback heuristic matching p1-flood/src/flood_score.py exactly."""
    RAINFALL_LOW, RAINFALL_HIGH = 50.0, 250.0
    ELEV_HIGH_RISK, ELEV_LOW_RISK = 50.0, 500.0
    RIVER_HIGH_RISK, RIVER_LOW_RISK = 1.0, 10.0

    # Rainfall factor
    if rainfall_7day_mm <= RAINFALL_LOW:
        rain_f = 0.05 * (rainfall_7day_mm / RAINFALL_LOW)
    elif rainfall_7day_mm >= RAINFALL_HIGH:
        rain_f = 0.95
    else:
        rain_f = 0.05 + ((rainfall_7day_mm - RAINFALL_LOW) / (RAINFALL_HIGH - RAINFALL_LOW)) * 0.9

    # Elevation factor
    if elevation_m is None:
        elev_f = 0.5
    elif elevation_m <= ELEV_HIGH_RISK:
        elev_f = 1.0
    elif elevation_m >= ELEV_LOW_RISK:
        elev_f = 0.0
    else:
        elev_f = 1.0 - ((elevation_m - ELEV_HIGH_RISK) / (ELEV_LOW_RISK - ELEV_HIGH_RISK))

    # River proximity factor
    if river_proximity_km is None:
        river_f = 0.5
    elif river_proximity_km <= RIVER_HIGH_RISK:
        river_f = 1.0
    elif river_proximity_km >= RIVER_LOW_RISK:
        river_f = 0.0
    else:
        river_f = 1.0 - ((river_proximity_km - RIVER_HIGH_RISK) / (RIVER_LOW_RISK - RIVER_HIGH_RISK))

    score = 0.60 * rain_f + 0.25 * river_f + 0.15 * elev_f
    return round(min(max(score, 0.0), 1.0), 3)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
p1_router = APIRouter(tags=["P1 Flood Intelligence"])


@p1_router.get("/api/v1/predictions/flood/health")
def p1_health():
    return {
        "status": "ok",
        "module": "p1-flood",
        "scoring_available": P1_SCORING_AVAILABLE,
        "data_dir_exists": P1_DATA_DIR.exists(),
    }


@p1_router.post("/api/v1/predictions/flood", response_model=FloodPredictionResponse)
def predict_flood(payload: FloodPredictionRequest):
    """
    Predict flood inundation risk for a given location.
    Uses the same mathematical model as p1-flood/src/flood_score.py.
    """
    lat = payload.latitude
    lon = payload.longitude
    segment_id = payload.segment_id or f"SEG_{lat:.2f}_{lon:.2f}"

    # Use provided values or sensible defaults based on NE India geography
    rainfall = payload.rainfall_7day_mm
    elevation = payload.elevation_m
    river_km = payload.river_proximity_km

    # If no rainfall provided, estimate from location (NE India monsoon baseline)
    if rainfall is None:
        # Rough monsoon baseline: lower elevation = more river valley rainfall
        if elevation is not None and elevation < 100:
            rainfall = 180.0  # Heavy valley rainfall
        elif elevation is not None and elevation > 500:
            rainfall = 80.0   # Moderate hill rainfall
        else:
            rainfall = 120.0  # Default monsoon baseline

    # If no elevation provided, estimate from latitude (rough NE India terrain)
    if elevation is None:
        if lat > 27.0:
            elevation = 800.0  # High altitude (Arunachal/Sikkim)
        elif lat > 26.0:
            elevation = 150.0  # Brahmaputra plains/hills
        else:
            elevation = 50.0   # Low-lying Barak/Tripura

    # If no river proximity, estimate (NE India is river-dense)
    if river_km is None:
        if elevation < 100:
            river_km = 1.5
        elif elevation < 300:
            river_km = 4.0
        else:
            river_km = 8.0

    # Compute probability
    if P1_SCORING_AVAILABLE:
        prob = compute_flood_probability(rainfall, elevation, river_km)
    else:
        prob = _compute_flood_fallback(rainfall, elevation, river_km)

    # Determine risk level
    if prob > 0.6:
        risk_level = "HIGH"
    elif prob > 0.3:
        risk_level = "MODERATE"
    else:
        risk_level = "LOW"

    now_iso = datetime.now(IST).isoformat()
    today = datetime.now(IST).date().isoformat()

    return FloodPredictionResponse(
        segment_id=segment_id,
        date=today,
        flood_probability=prob,
        confidence=0.65 if elevation is not None else 0.4,
        risk_level=risk_level,
        contributing_factors={
            "rainfall_7day_mm": round(rainfall, 1),
            "elevation_m": round(elevation, 1) if elevation else None,
            "river_proximity_km": round(river_km, 1) if river_km else None,
            "historical_flood_frequency": None,
            "scoring_method": "p1_heuristic" if P1_SCORING_AVAILABLE else "fallback_heuristic",
        },
        source_timestamp=now_iso,
        coordinates=[lat, lon],
    )


@p1_router.get("/api/v1/predictions/flood/sample")
def flood_sample_output():
    """Return cached sample output if available."""
    sample_path = P1_DATA_DIR / "sample_output.json"
    if sample_path.exists():
        with open(sample_path) as f:
            return json.load(f)
    raise HTTPException(status_code=404, detail="Sample output not generated yet. Run flood_score.py first.")
