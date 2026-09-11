"""
Combines rainfall + real terrain data (elevation, river proximity) into a
flood_probability score per segment, matching the schema in
docs/api-contracts.md.

Rainfall comes from fetch_rainfall.py (Open-Meteo, real).
Terrain comes from fetch_terrain.py (Open-Meteo elevation + OSM Overpass, real).
Historical flood frequency is still a placeholder (`null`) until a defensible
frequency lookup is built. The trained model is used when its artifact exists;
the transparent heuristic remains the fallback when it does not.
"""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "p1_flood_model.joblib"
IST = timezone(timedelta(hours=5, minutes=30))

# --- Rainfall thresholds ---
RAINFALL_LOW_MM = 50
RAINFALL_HIGH_MM = 250

# --- Elevation thresholds (metres) --- lower elevation = higher flood risk
ELEVATION_HIGH_RISK_M = 50     # at/below this -> max risk contribution
ELEVATION_LOW_RISK_M = 500     # at/above this -> ~no risk contribution

# --- River proximity thresholds (km) --- closer to a river = higher risk
RIVER_HIGH_RISK_KM = 1.0       # at/below this -> max risk contribution
RIVER_LOW_RISK_KM = 10.0       # at/above this -> ~no risk contribution

# How much each factor contributes to the final score. Rainfall is the main
# driver; terrain adjusts it up/down. Tune these once you have real labeled
# flood outcomes to check against.
WEIGHT_RAINFALL = 0.6
WEIGHT_RIVER = 0.25
WEIGHT_ELEVATION = 0.15


def _rainfall_factor(past_7day_rainfall_mm: float) -> float:
    """Normalize cumulative 7-day rainfall into [0, 1]."""
    if past_7day_rainfall_mm <= RAINFALL_LOW_MM:
        return 0.05 * (past_7day_rainfall_mm / RAINFALL_LOW_MM)
    if past_7day_rainfall_mm >= RAINFALL_HIGH_MM:
        return 0.95
    span = RAINFALL_HIGH_MM - RAINFALL_LOW_MM
    frac = (past_7day_rainfall_mm - RAINFALL_LOW_MM) / span
    return 0.05 + frac * 0.9


def _river_factor(river_proximity_km: float | None) -> float:
    """Closer to a river -> closer to 1. Unknown -> neutral 0.5."""
    if river_proximity_km is None:
        return 0.5
    if river_proximity_km <= RIVER_HIGH_RISK_KM:
        return 1.0
    if river_proximity_km >= RIVER_LOW_RISK_KM:
        return 0.0
    span = RIVER_LOW_RISK_KM - RIVER_HIGH_RISK_KM
    return 1.0 - ((river_proximity_km - RIVER_HIGH_RISK_KM) / span)


def _elevation_factor(elevation_m: float | None) -> float:
    """Lower elevation -> closer to 1. Unknown -> neutral 0.5."""
    if elevation_m is None:
        return 0.5
    if elevation_m <= ELEVATION_HIGH_RISK_M:
        return 1.0
    if elevation_m >= ELEVATION_LOW_RISK_M:
        return 0.0
    span = ELEVATION_LOW_RISK_M - ELEVATION_HIGH_RISK_M
    return 1.0 - ((elevation_m - ELEVATION_HIGH_RISK_M) / span)


def compute_flood_probability(
    past_7day_rainfall_mm: float,
    elevation_m: float | None = None,
    river_proximity_km: float | None = None,
) -> float:
    """
    Combines rainfall, elevation, and river proximity into one [0, 1] score.
    Each factor is normalized separately, then combined with fixed weights.
    Still a hand-built formula, not a trained model - but every input is real.
    """
    rainfall_f = _rainfall_factor(past_7day_rainfall_mm)
    river_f = _river_factor(river_proximity_km)
    elevation_f = _elevation_factor(elevation_m)

    score = (
        WEIGHT_RAINFALL * rainfall_f
        + WEIGHT_RIVER * river_f
        + WEIGHT_ELEVATION * elevation_f
    )
    return round(min(max(score, 0.0), 1.0), 3)


def _ml_probability(
    rainfall: list[float],
    elevation_m: float | None,
    river_proximity_km: float | None,
    latitude: float | None,
    longitude: float | None,
    prediction_date: str,
) -> float | None:
    """Use the trained model when available; return None until then."""
    if not MODEL_PATH.exists():
        return None
    try:
        from ml_model import load_model, predict_probability

        past = [float(value) for value in rainfall if value is not None]
        features = {
            "rainfall_1d_mm": past[-1] if past else None,
            "rainfall_3d_mm": sum(past[-3:]) if past else None,
            "rainfall_7d_mm": sum(past[-7:]) if len(past) >= 7 else None,
            "rainfall_14d_mm": sum(past[-14:]) if len(past) >= 14 else None,
            "rainfall_30d_mm": sum(past[-30:]) if len(past) >= 30 else None,
            "rainfall_anomaly_7d": None,
            "rainfall_anomaly_30d": None,
            "elevation_m": elevation_m,
            "river_proximity_km": river_proximity_km,
            "latitude": latitude,
            "longitude": longitude,
            "month": int(prediction_date[5:7]),
        }
        artifact = load_model(MODEL_PATH)
        return predict_probability(features, artifact) if artifact else None
    except (ImportError, OSError, ValueError, KeyError, IndexError):
        # A corrupt/unavailable optional artifact must not take down the
        # live heuristic path. Training and CI surface these errors directly.
        return None


def _ml_model_version() -> str | None:
    if not MODEL_PATH.exists():
        return None
    try:
        from ml_model import load_model

        artifact = load_model(MODEL_PATH)
        return artifact.get("model_version") if artifact else None
    except (ImportError, OSError, ValueError, KeyError):
        return None


def load_json(filename: str, required: bool = True) -> list[dict]:
    path = DATA_DIR / filename
    if not path.exists():
        if required:
            raise FileNotFoundError(f"{path} not found — run fetch_rainfall.py / fetch_terrain.py first.")
        return []
    with open(path) as f:
        return json.load(f)


def build_outputs(rainfall_data: list[dict], terrain_data: list[dict]) -> list[dict]:
    outputs = []
    today = datetime.now(IST).date().isoformat()
    now_iso = datetime.now(IST).isoformat()

    # index terrain by segment_id so we can look it up per location
    terrain_by_segment = {t["segment_id"]: t for t in terrain_data}

    for loc in rainfall_data:
        precip = loc.get("precipitation_mm", [])

        past_days = int(loc.get("past_days", 7))
        historical = precip[:past_days]
        # The most recent historical observations are the final 7 values before
        # the forecast window, regardless of the requested history length.
        past_week = [p for p in historical[-7:] if p is not None]
        rainfall_7day = sum(past_week) if past_week else 0.0

        terrain = terrain_by_segment.get(loc["segment_id"], {})
        elevation_m = terrain.get("elevation_m")
        river_km = terrain.get("river_proximity_km")

        heuristic_prob = compute_flood_probability(rainfall_7day, elevation_m, river_km)
        ml_prob = _ml_probability(
            historical,
            elevation_m,
            river_km,
            loc.get("lat"),
            loc.get("lon"),
            today,
        )
        prob = ml_prob if ml_prob is not None else heuristic_prob
        model_version = _ml_model_version() if ml_prob is not None else None

        # confidence is higher now that terrain is real too - still capped
        # below 1.0 because historical flood frequency is still missing
        confidence = 0.65 if terrain else 0.4

        outputs.append(
            {
                "segment_id": loc["segment_id"],
                "date": today,
                "flood_probability": prob,
                "confidence": confidence,
                "contributing_factors": {
                    "rainfall_7day_mm": round(rainfall_7day, 1),
                    "elevation_m": elevation_m,
                    "river_proximity_km": river_km,
                    "historical_flood_frequency": None,  # TODO: real historical dataset
                    "scoring_method": "ml_calibrated" if ml_prob is not None else "heuristic_fallback",
                    "model_version": model_version,
                },
                "source_timestamp": now_iso,
            }
        )
    return outputs


def main():
    rainfall_data = load_json("rainfall_raw.json", required=True)
    terrain_data = load_json("terrain_raw.json", required=False)
    if not terrain_data:
        print("  NOTE: terrain_raw.json not found — run fetch_terrain.py for real "
              "elevation/river data. Scoring without it for now (neutral 0.5 factors).")

    outputs = build_outputs(rainfall_data, terrain_data)

    out_path = DATA_DIR / "sample_output.json"
    with open(out_path, "w") as f:
        json.dump(outputs, f, indent=2)

    print(f"Wrote {len(outputs)} flood_probability records to {out_path}")
    for o in outputs:
        print(f"  {o['segment_id']}: {o['flood_probability']}")


if __name__ == "__main__":
    main()
