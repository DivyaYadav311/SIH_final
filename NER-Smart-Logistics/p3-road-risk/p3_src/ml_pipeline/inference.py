from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from .pipeline import FEATURE_COLUMNS, MODEL_ROOT
from p3_src.hybrid import compute_hybrid_disruption


def load_current_model() -> tuple[Any, dict[str, Any]]:
    current_path = MODEL_ROOT / "current_model.json"
    if not current_path.exists():
        raise RuntimeError("current_model.json is missing")
    current = json.loads(current_path.read_text())
    version = current.get("model_version")
    artifact = MODEL_ROOT.parent / current.get("artifact", "")
    metadata_path = MODEL_ROOT / f"{version}_metadata.json"
    if not version or not artifact.exists() or not metadata_path.exists():
        raise RuntimeError("active model artifact or metadata is missing")
    metadata = json.loads(metadata_path.read_text())
    if metadata.get("model_version") != version:
        raise RuntimeError("active model version does not match metadata")
    if metadata.get("target_name") != "severity_risk_target":
        raise RuntimeError("active model is not the supported accident-severity model")
    schema_path = MODEL_ROOT / "feature_schema.json"
    if not schema_path.exists():
        raise RuntimeError("feature_schema.json is missing")
    schema = json.loads(schema_path.read_text())
    if schema.get("features") != metadata.get("feature_names"):
        raise RuntimeError("model metadata and feature schema disagree")
    model = joblib.load(artifact)
    if not hasattr(model, "predict_proba"):
        raise RuntimeError("active model does not provide probabilities")
    return model, metadata


def predict_severity_risk(values: dict[str, Any]) -> dict[str, Any]:
    model, metadata = load_current_model()
    feature_names = metadata["feature_names"]
    row = {feature: values.get(feature) for feature in feature_names}
    frame = pd.DataFrame([row], columns=feature_names)
    probability = float(model.predict_proba(frame)[:, 1][0])
    probability = max(0.0, min(1.0, probability))
    hybrid = compute_hybrid_disruption({
        "road_id": values.get("road_id", "unnamed"),
        "timestamp": values.get("timestamp"),
        "upstream_predictions": {
            "flood_probability": values.get("flood_probability"),
            "landslide_probability": values.get("landslide_probability"),
        },
        "traffic_risk": {
            "risk_probability": probability,
            "incident_factor": values.get("incident_risk"),
            "congestion_factor": values.get("congestion_factor"),
            "nearby_accident_factor": values.get("nearby_accident_factor"),
            "nearby_accident_factor_metadata": {
                "distance_km": values.get("nearby_accident_distance_km"),
                "event_timestamp": values.get("nearby_accident_event_timestamp"),
            },
        },
        "environment": {
            "rainfall_intensity_factor": values.get("rainfall_intensity_factor"),
            "river_level_factor": values.get("river_level_factor"),
        },
        "terrain": {
            "slope_factor": values.get("slope_factor"),
            "terrain_susceptibility_factor": values.get("terrain_susceptibility_factor"),
        },
        "road_vulnerability": {
            "flood_vulnerability_factor": values.get("flood_vulnerability_factor"),
            "road_type_vulnerability_factor": values.get("road_type_vulnerability_factor"),
            "road_vulnerability_factor": values.get("road_vulnerability_factor"),
        },
        "incidents": {
            "nearby_landslide_factor": values.get("nearby_landslide_factor"),
            "nearby_flood_factor": values.get("nearby_flood_factor"),
            "nearby_accident_factor": values.get("nearby_accident_factor"),
            "nearby_flood_factor_metadata": {"distance_km": values.get("nearby_flood_distance_km"), "event_timestamp": values.get("nearby_flood_event_timestamp")},
            "nearby_landslide_factor_metadata": {"distance_km": values.get("nearby_landslide_distance_km"), "event_timestamp": values.get("nearby_landslide_event_timestamp")},
        },
    })
    return {
        "risk_probability": hybrid["risk_probability"],
        "operational_disruption_score": hybrid["operational_disruption_score"],
        "accessibility_score": hybrid["accessibility_score"],
        "disruption_probability": hybrid["disruption_probability"],
        "disruption_method": hybrid["disruption_method"],
        "disruption_category": hybrid["disruption_category"],
        "evidence_completeness": hybrid["evidence_completeness"],
        "disruption_confidence": hybrid["disruption_confidence"],
        "components": hybrid["components"],
        "factors": hybrid["factors"],
        "evidence": hybrid["evidence"],
        "explanation": hybrid["explanation"],
        "score_components": hybrid["components"],
        "score_contributions": hybrid["score_contributions"],
        "score_weights": hybrid["score_weights"],
        "available_components": [name for name, value in hybrid["score_contributions"].items() if value != 0.0],
        "weight_method": "deterministic_evidence_fusion",
        "weight_source": "deterministic_evidence_fusion",
        "weight_version": hybrid.get("config_version", "p3_hybrid_v2"),
        "model_version": metadata["model_version"],
        "risk_target": metadata["target_definition"],
        "road_disruption_model_status": "insufficient_labels",
    }


def current_model_info() -> dict[str, Any]:
    _, metadata = load_current_model()
    return {
        "model_version": metadata["model_version"],
        "model_type": metadata.get("model_type"),
        "target": metadata.get("target_name"),
        "target_definition": metadata.get("target_definition"),
        "feature_names": metadata.get("feature_names", []),
        "metrics": metadata.get("metrics", {}),
        "road_disruption_model_status": "insufficient_labels",
    }
