from datetime import datetime, timezone
import uuid

from fastapi import FastAPI, HTTPException

from app.live_data import collect_live_features, data_sources
from app.schemas import LandslideRequest, LandslidePrediction, LiveFeatures
from app.scoring import model_status, predict_landslide_risk
from app.satellite_data import collect_satellite_observation

app = FastAPI(
    title="Live Landslide Prediction Agent",
    description=(
        "Fetches live weather, terrain, land-cover and historical landslide "
        "features from public APIs, then predicts landslide risk."
    ),
    version="2.0.0",
)


@app.get("/health")
def health_check():
    return {"status": "ok", "mode": "live-api"}


@app.get("/api/v1/model-status")
def get_model_status():
    """Show whether predictions currently use a trained model or the fallback."""
    return model_status()


@app.get("/api/v1/satellite-observation")
def satellite_observation(latitude: float, longitude: float):
    """Return Sentinel-2 scene metadata without affecting predictions."""
    return {
        "latitude": latitude,
        "longitude": longitude,
        "satellite_observation": collect_satellite_observation(latitude, longitude),
    }


@app.get("/api/v1/live-features")
def live_features(latitude: float, longitude: float):
    """Debug/inspection endpoint showing exactly what the live APIs return."""
    try:
        features = collect_live_features(latitude, longitude)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Live data fetch failed: {exc}") from exc
    source_status = features.pop("source_status")
    return {
        "latitude": latitude,
        "longitude": longitude,
        "features": features,
        "data_sources": data_sources(),
        "source_status": source_status,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


@app.post("/api/v1/predictions/landslide", response_model=LandslidePrediction)
def predict_landslide(payload: LandslideRequest):
    try:
        features = collect_live_features(payload.latitude, payload.longitude)
        probability, risk_level, confidence, model_version = predict_landslide_risk(features)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Live prediction failed: {exc}") from exc

    source_status = features.pop("source_status")
    satellite = collect_satellite_observation(payload.latitude, payload.longitude)
    location_id = payload.location_id or (
        f"LOC_{payload.latitude:.4f}_{payload.longitude:.4f}"
    )
    return LandslidePrediction(
        location_id=location_id,
        latitude=payload.latitude,
        longitude=payload.longitude,
        landslide_probability=round(probability, 4),
        risk_level=risk_level,
        confidence=round(confidence, 4),
        model_version=model_version,
        timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        live_features=LiveFeatures(**features),
        data_sources=data_sources(),
        source_status=source_status,
        satellite_observation=satellite,
    )
