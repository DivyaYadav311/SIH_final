"""Landslide risk scoring.

The default is a transparent heuristic until a real trained classifier is
provided. A joblib model with predict_proba can be dropped into MODEL_PATH.
"""

import math
import os
from typing import Any, Tuple

MODEL_VERSION_HEURISTIC = "landslide_heuristic_v0"
MODEL_VERSION_TRAINED = os.environ.get("MODEL_VERSION", "landslide_logistic_regression_v1")
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_UNIFIED_MODEL = os.path.join(_ROOT, "models", "p2_landslide", "landslide_model_v1.pkl")
_LOCAL_MODEL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models", "landslide_model_v1.pkl")
MODEL_PATH = os.environ.get("MODEL_PATH", _UNIFIED_MODEL if os.path.exists(_UNIFIED_MODEL) else _LOCAL_MODEL)

FEATURE_ORDER = [
    "latitude", "longitude",
    "rainfall_1h_mm", "rainfall_6h_mm", "rainfall_24h_mm", "rainfall_7d_mm",
    "temperature_c", "humidity_percent", "elevation_m", "slope_degree",
    "aspect_degree", "historical_landslide_count",
]

LAND_COVER_RISK_MULTIPLIER = {
    "forest": 0.85,
    "grassland": 1.0,
    "shrubland": 1.0,
    "cropland": 1.1,
    "wetland": 1.05,
    "barren": 1.25,
    "urban": 0.9,
    "snow_ice": 0.7,
}

_trained_model = None
_trained_model_load_attempted = False
_trained_model_metadata: dict[str, Any] | None = None


def _try_load_trained_model():
    global _trained_model, _trained_model_load_attempted, _trained_model_metadata
    if _trained_model_load_attempted:
        return _trained_model
    _trained_model_load_attempted = True
    if not os.path.exists(MODEL_PATH):
        return None
    try:
        import joblib
        artifact = joblib.load(MODEL_PATH)
        _trained_model = artifact
        if isinstance(artifact, dict):
            if artifact.get("feature_order") != FEATURE_ORDER:
                _trained_model = None
            else:
                _trained_model = artifact.get("model")
                _trained_model_metadata = {
                    "artifact_version": artifact.get("artifact_version"),
                    "created_at": artifact.get("created_at"),
                    "model_type": artifact.get("model_type", "unknown"),
                    "model_version": artifact.get("model_version", MODEL_VERSION_TRAINED),
                    "training_data_kind": artifact.get("training_data_kind", "verified_observations"),
                    "metrics": artifact.get("metrics", {}),
                }
    except Exception:
        _trained_model = None
    return _trained_model


def model_status() -> dict[str, Any]:
    """Return whether a compatible trained artifact is active, without scoring."""
    model = _try_load_trained_model()
    if model is None:
        return {
            "mode": "heuristic",
            "model_version": MODEL_VERSION_HEURISTIC,
            "model_path": MODEL_PATH,
            "message": "No compatible trained model artifact is loaded.",
        }
    return {
        "mode": "trained",
        "model_version": MODEL_VERSION_TRAINED,
        "model_path": MODEL_PATH,
        **(_trained_model_metadata or {}),
    }


def _sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def _get(f: dict[str, Any], name: str) -> float:
    return float(f[name])


def _heuristic_score(f: dict[str, Any]) -> Tuple[float, float]:
    rain_1h_n = min(_get(f, "rainfall_1h_mm") / 60.0, 1.0)
    rain_6h_n = min(_get(f, "rainfall_6h_mm") / 150.0, 1.0)
    rain_24h_n = min(_get(f, "rainfall_24h_mm") / 300.0, 1.0)
    rain_7d_n = min(_get(f, "rainfall_7d_mm") / 700.0, 1.0)
    slope_n = min(_get(f, "slope_degree") / 55.0, 1.0)
    hist_n = min(_get(f, "historical_landslide_count") / 5.0, 1.0)
    humidity_n = max(0.0, (_get(f, "humidity_percent") - 50.0) / 50.0)

    raw = (
        0.20 * rain_1h_n +
        0.10 * rain_6h_n +
        0.20 * rain_24h_n +
        0.15 * rain_7d_n +
        0.25 * slope_n +
        0.07 * hist_n +
        0.03 * humidity_n
    )

    multiplier = LAND_COVER_RISK_MULTIPLIER.get(str(f.get("land_cover")), 1.0)
    adjusted = raw * multiplier
    probability = _sigmoid(8.0 * (adjusted - 0.40))

    signals = [rain_24h_n, rain_7d_n, slope_n, hist_n]
    mean_signal = sum(signals) / len(signals)
    variance = sum((s - mean_signal) ** 2 for s in signals) / len(signals)
    agreement = 1.0 - min(variance * 4, 0.5)
    confidence = 0.55 + 0.35 * agreement

    return min(max(probability, 0.0), 1.0), min(max(confidence, 0.0), 0.99)


def _risk_level(probability: float) -> str:
    if probability >= 0.75:
        return "CRITICAL"
    if probability >= 0.50:
        return "HIGH"
    if probability >= 0.25:
        return "MODERATE"
    return "LOW"


def predict_landslide_risk(f: dict[str, Any]) -> Tuple[float, str, float, str]:
    model = _try_load_trained_model()
    if model is not None:
        vector = [[float(f[name]) for name in FEATURE_ORDER]]
        try:
            probability = float(model.predict_proba(vector)[0][1])
            # Inventory-only susceptibility is less certain than a model
            # validated with dated event and verified non-event observations.
            confidence = (
                0.65
                if (_trained_model_metadata or {}).get("training_data_kind")
                == "gsi_inventory_with_pseudo_absences"
                else 0.90
            )
            version = (_trained_model_metadata or {}).get("model_version", MODEL_VERSION_TRAINED)
            return probability, _risk_level(probability), confidence, version
        except Exception:
            pass

    probability, confidence = _heuristic_score(f)
    return probability, _risk_level(probability), confidence, MODEL_VERSION_HEURISTIC
