from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
_UNIFIED_CONFIG = ROOT.parent / "models" / "p3_road_risk" / "hybrid_weight_config.json"
_LOCAL_CONFIG = ROOT / "models" / "hybrid_weight_config.json"
CONFIG_PATH = _UNIFIED_CONFIG if _UNIFIED_CONFIG.exists() else _LOCAL_CONFIG


def _as_float(value: Any, *, name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{name} must be numeric")
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be numeric") from None
    if not math.isfinite(numeric):
        raise ValueError(f"{name} must be finite")
    return numeric


def _require_factor(value: Any, *, field: str) -> float | None:
    numeric = _as_float(value, name=field)
    if numeric is not None and not 0.0 <= numeric <= 1.0:
        raise ValueError(f"{field} must be in [0,1]")
    return numeric


def _require_non_negative(value: Any, *, field: str) -> float:
    numeric = _as_float(value, name=field)
    if numeric is None or numeric < 0.0:
        raise ValueError(f"{field} must be a non-negative number")
    return numeric


def _mapping(value: Any, *, field: str) -> Mapping[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
    return value


def _resolve_component(payload: Mapping[str, Any], *paths: str) -> Any:
    for path in paths:
        if path in payload and payload[path] is not None:
            return payload[path]
    return None


def _normalize_available_weights(weights: Mapping[str, Any], available_keys: list[str]) -> dict[str, float]:
    available = {
        key: float(weights[key])
        for key in available_keys
        if key in weights and float(weights[key]) > 0.0
    }
    total = sum(available.values())
    return {key: value / total for key, value in available.items()} if total else {}


def _weighted_average(components: Mapping[str, float | None], weights: Mapping[str, Any]) -> tuple[float | None, dict[str, float]]:
    available = {key: value for key, value in components.items() if value is not None}
    if not available:
        return None, {}
    effective = _normalize_available_weights(weights, list(available))
    if not effective:
        return None, {}
    return sum(effective[key] * available[key] for key in effective), effective


def load_hybrid_config() -> dict[str, Any]:
    config = json.loads(CONFIG_PATH.read_text())
    hazard_weights = config.get("hazard_weights") or {}
    if not hazard_weights or any(float(value) < 0 for value in hazard_weights.values()):
        raise RuntimeError("hybrid weights must be non-negative")
    if not math.isclose(sum(float(value) for value in hazard_weights.values()), 1.0, rel_tol=1e-9, abs_tol=1e-9):
        raise RuntimeError("hybrid weights must sum to one")
    return config


def compute_proximity_factor(distance_km: Any, scale_km: Any = 5.0) -> float:
    distance = _require_non_negative(distance_km, field="distance_km")
    scale = _require_non_negative(scale_km, field="scale_km")
    if scale == 0.0:
        raise ValueError("scale_km must be greater than zero")
    return max(0.0, min(1.0, math.exp(-distance / scale)))


def _parse_timestamp(value: Any, *, field: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError(f"{field} must be an ISO-8601 timestamp") from None
    else:
        raise ValueError(f"{field} must be an ISO-8601 timestamp")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def compute_temporal_decay(event_timestamp: Any, prediction_timestamp: Any, tau_hours: Any = 24.0) -> float:
    event_time = _parse_timestamp(event_timestamp, field="event_timestamp")
    prediction_time = _parse_timestamp(prediction_timestamp, field="prediction_timestamp")
    tau = _require_non_negative(tau_hours, field="tau_hours")
    if tau == 0.0:
        raise ValueError("tau_hours must be greater than zero")
    age_hours = (prediction_time - event_time).total_seconds() / 3600.0
    if age_hours < 0.0:
        raise ValueError("future event cannot influence a prediction")
    return max(0.0, min(1.0, math.exp(-age_hours / tau)))


def _event_modifier(event: Mapping[str, Any], prediction_timestamp: Any, config: Mapping[str, Any]) -> tuple[float, bool, bool]:
    spatial = 1.0
    temporal = 1.0
    has_spatial = False
    has_temporal = False
    if event.get("distance_km") is not None:
        spatial = compute_proximity_factor(event["distance_km"], config.get("spatial_decay", {}).get("scale_km", 5.0))
        has_spatial = True
    if event.get("event_timestamp") is not None:
        if prediction_timestamp is None:
            raise ValueError("prediction timestamp is required for temporal incident evidence")
        temporal = compute_temporal_decay(event["event_timestamp"], prediction_timestamp, config.get("temporal_decay", {}).get("tau_hours", 24.0))
        has_temporal = True
    return spatial * temporal, has_spatial, has_temporal


def _incident_factor(incidents: Mapping[str, Any], key: str, aliases: tuple[str, ...], prediction_timestamp: Any, config: Mapping[str, Any]) -> tuple[float | None, bool, bool]:
    raw = _resolve_component(incidents, key, *aliases)
    event = _mapping(incidents.get(f"{key}_metadata"), field=f"{key}_metadata")
    if raw is None and event.get("factor") is not None:
        raw = event["factor"]
    factor = _require_factor(raw, field=key)
    if factor is None:
        return None, False, False
    modifier, has_spatial, has_temporal = _event_modifier(event, prediction_timestamp, config)
    return factor * modifier, has_spatial, has_temporal


def _score_category(value: float) -> str:
    if value < 0.25:
        return "LOW"
    if value < 0.50:
        return "MODERATE"
    if value < 0.75:
        return "HIGH"
    return "CRITICAL"


def _confidence_from_completeness(value: float) -> str:
    if value < 0.50:
        return "LOW"
    if value < 0.80:
        return "MEDIUM"
    return "HIGH"


def compute_operational_disruption_score(components: dict[str, float | None]) -> dict[str, Any]:
    """Retained legacy scorer; the prediction API uses compute_hybrid_disruption."""
    config = load_hybrid_config()
    configured = config.get("weights", {})
    available = {
        name: _require_factor(value, field=name)
        for name, value in components.items()
        if value is not None and float(configured.get(name, 0.0)) > 0.0
    }
    available = {name: value for name, value in available.items() if value is not None}
    total = sum(float(configured[name]) for name in available)
    if not available or total <= 0.0:
        return {"operational_disruption_score": None, "accessibility_score": None, "score_components": components, "score_contributions": {}, "score_weights": {}, "available_components": [], "weight_method": config.get("method"), "weight_source": config.get("weight_source"), "weight_version": config.get("version")}
    weights = {name: float(configured[name]) / total for name in available}
    contributions = {name: weights[name] * available[name] for name in available}
    score = sum(contributions.values())
    return {"operational_disruption_score": score, "accessibility_score": 100.0 * (1.0 - score), "score_components": components, "score_contributions": contributions, "score_weights": weights, "available_components": list(available), "weight_method": config.get("method"), "weight_source": config.get("weight_source"), "weight_version": config.get("version")}


def compute_hybrid_disruption(payload: dict[str, Any]) -> dict[str, Any]:
    input_payload = _mapping(payload, field="payload")
    predictions = _mapping(input_payload.get("upstream_predictions"), field="upstream_predictions")
    traffic = _mapping(input_payload.get("traffic_risk"), field="traffic_risk")
    environment = _mapping(input_payload.get("environment"), field="environment")
    terrain = _mapping(input_payload.get("terrain"), field="terrain")
    vulnerability = _mapping(input_payload.get("road_vulnerability"), field="road_vulnerability")
    incidents = _mapping(input_payload.get("incidents"), field="incidents")
    config = load_hybrid_config()
    prediction_timestamp = input_payload.get("timestamp")

    flood_probability = _require_factor(_resolve_component(predictions, "flood_probability", "flood_prob"), field="flood_probability")
    landslide_probability = _require_factor(_resolve_component(predictions, "landslide_probability", "landslide_prob"), field="landslide_probability")
    risk_probability = _require_factor(_resolve_component(traffic, "risk_probability", "risk_prob"), field="risk_probability")
    rainfall = _require_factor(_resolve_component(environment, "rainfall_intensity_factor", "rainfall_factor"), field="rainfall_intensity_factor")
    river = _require_factor(_resolve_component(environment, "river_level_factor", "river_factor"), field="river_level_factor")
    slope = _require_factor(_resolve_component(terrain, "slope_factor", "slope"), field="slope_factor")
    terrain_factor = _require_factor(_resolve_component(terrain, "terrain_susceptibility_factor", "terrain_factor"), field="terrain_susceptibility_factor")
    flood_vulnerability = _require_factor(_resolve_component(vulnerability, "flood_vulnerability_factor", "flood_vulnerability"), field="flood_vulnerability_factor")
    road_type_vulnerability = _require_factor(_resolve_component(vulnerability, "road_type_vulnerability_factor", "road_type_vulnerability"), field="road_type_vulnerability_factor")
    explicit_vulnerability = _require_factor(_resolve_component(vulnerability, "road_vulnerability_factor", "vulnerability_factor"), field="road_vulnerability_factor")
    road_vulnerability = explicit_vulnerability if explicit_vulnerability is not None else road_type_vulnerability
    congestion = _require_factor(_resolve_component(traffic, "congestion_factor", "congestion"), field="congestion_factor")
    nearby_landslide, landslide_spatial, landslide_temporal = _incident_factor(incidents, "nearby_landslide_factor", ("nearby_landslide",), prediction_timestamp, config)
    nearby_flood, flood_spatial, flood_temporal = _incident_factor(incidents, "nearby_flood_factor", ("nearby_flood",), prediction_timestamp, config)
    nearby_accident, accident_spatial, accident_temporal = _incident_factor(traffic, "nearby_accident_factor", ("nearby_accident",), prediction_timestamp, config)
    if nearby_accident is None:
        nearby_accident = _require_factor(_resolve_component(incidents, "nearby_accident_factor", "nearby_accident"), field="nearby_accident_factor")

    flood_environment, flood_effective_weights = _weighted_average({"rainfall": rainfall, "river": river, "flood_vulnerability": flood_vulnerability, "nearby_flood": nearby_flood}, config["flood_weights"])
    landslide_environment, landslide_effective_weights = _weighted_average({"rainfall": rainfall, "slope": slope, "terrain": terrain_factor, "nearby_landslide": nearby_landslide}, config["landslide_weights"])
    traffic_environment, traffic_effective_weights = _weighted_average({"risk": risk_probability, "nearby_accident": nearby_accident, "congestion": congestion}, config["traffic_weights"])
    flood_disruption = flood_probability * flood_environment if flood_probability is not None and flood_environment is not None else None
    landslide_disruption = landslide_probability * landslide_environment if landslide_probability is not None and landslide_environment is not None else None
    traffic_disruption = traffic_environment
    available_components = {key: value for key, value in {"flood": flood_disruption, "landslide": landslide_disruption, "traffic": traffic_disruption}.items() if value is not None}
    top_weights = _normalize_available_weights(config["hazard_weights"], list(available_components))
    raw_disruption = sum(top_weights[key] * value for key, value in available_components.items()) if available_components else 0.0

    synergy_config = config.get("synergy", {})
    synergy_bonus = 0.0
    if synergy_config.get("enabled", True) and flood_probability is not None and landslide_probability is not None:
        threshold = float(synergy_config.get("threshold", 0.50))
        synergy_bonus = float(synergy_config.get("max_bonus", 0.10)) * max(0.0, min(1.0, (min(flood_probability, landslide_probability) - threshold) * 2.0))
    pre_modifier = raw_disruption + synergy_bonus
    vulnerability_config = config.get("road_vulnerability_modifier", {})
    vulnerability_modifier = 1.0
    if vulnerability_config.get("enabled", True) and road_vulnerability is not None:
        minimum = float(vulnerability_config.get("minimum", 0.90))
        maximum = float(vulnerability_config.get("maximum", 1.10))
        vulnerability_modifier = max(minimum, min(maximum, minimum + (maximum - minimum) * road_vulnerability))
    final_disruption = max(0.0, min(1.0, pre_modifier * vulnerability_modifier))

    core_names = ("flood_probability", "landslide_probability", "risk_probability", "rainfall", "river", "slope", "terrain", "road_vulnerability", "nearby_flood", "nearby_landslide", "nearby_accident", "congestion")
    core_values = (flood_probability, landslide_probability, risk_probability, rainfall, river, slope, terrain_factor, road_vulnerability, nearby_flood, nearby_landslide, nearby_accident, congestion)
    completeness = sum(value is not None for value in core_values) / len(core_values)
    driver_scores = {"flood": flood_disruption or 0.0, "landslide": landslide_disruption or 0.0, "traffic": traffic_disruption or 0.0}
    ranked = sorted(driver_scores, key=driver_scores.get, reverse=True)
    key_factors = []
    if landslide_probability is not None and landslide_probability >= 0.50: key_factors.append("high landslide probability")
    if flood_probability is not None and flood_probability >= 0.50: key_factors.append("elevated flood probability")
    if rainfall is not None and rainfall >= 0.50: key_factors.append("high rainfall")
    if slope is not None and slope >= 0.50: key_factors.append("steep terrain")
    if nearby_flood is not None and nearby_flood >= 0.50: key_factors.append("nearby flood evidence")
    if nearby_landslide is not None and nearby_landslide >= 0.50: key_factors.append("nearby landslide evidence")
    if nearby_accident is not None and nearby_accident >= 0.50: key_factors.append("nearby accident evidence")
    missing = [name for name, value in zip(core_names, core_values) if value is None]
    evidence = {"flood": flood_probability is not None, "landslide": landslide_probability is not None, "rainfall": rainfall is not None, "river": river is not None, "terrain": slope is not None or terrain_factor is not None, "road_vulnerability": road_vulnerability is not None, "traffic": risk_probability is not None or congestion is not None or nearby_accident is not None, "incidents": any(value is not None for value in (nearby_flood, nearby_landslide, nearby_accident)), "spatial_context": flood_spatial or landslide_spatial or accident_spatial, "temporal_context": flood_temporal or landslide_temporal or accident_temporal}
    score_contributions = {"flood": top_weights.get("flood", 0.0) * (flood_disruption or 0.0) * vulnerability_modifier, "landslide": top_weights.get("landslide", 0.0) * (landslide_disruption or 0.0) * vulnerability_modifier, "traffic": top_weights.get("traffic", 0.0) * (traffic_disruption or 0.0) * vulnerability_modifier, "synergy": synergy_bonus * vulnerability_modifier}
    confidence = _confidence_from_completeness(completeness)
    return {
        "road_id": input_payload.get("road_id", "unknown"), "timestamp": prediction_timestamp, "risk_probability": risk_probability, "disruption_probability": final_disruption, "operational_disruption_score": final_disruption, "disruption_category": _score_category(final_disruption), "evidence_completeness": completeness, "disruption_confidence": confidence, "evidence_confidence": confidence, "disruption_method": "hybrid_evidence_fusion_v2", "raw_disruption": raw_disruption, "pre_modifier_disruption": pre_modifier,
        "flood_disruption": flood_disruption, "landslide_disruption": landslide_disruption, "traffic_disruption": traffic_disruption, "synergy_bonus": synergy_bonus, "final_disruption": final_disruption,
        "components": {"flood_disruption": flood_disruption, "landslide_disruption": landslide_disruption, "traffic_disruption": traffic_disruption, "synergy_bonus": synergy_bonus, "road_vulnerability_modifier": vulnerability_modifier},
        "factors": {"flood_probability": flood_probability, "landslide_probability": landslide_probability, "risk_probability": risk_probability, "rainfall_factor": rainfall, "river_factor": river, "slope_factor": slope, "terrain_factor": terrain_factor, "road_vulnerability": road_vulnerability, "nearby_flood_factor": nearby_flood, "nearby_landslide_factor": nearby_landslide, "nearby_accident_factor": nearby_accident, "congestion_factor": congestion},
        "score_contributions": score_contributions, "score_weights": top_weights, "available_components": list(available_components), "evidence": evidence, "explanation": {"primary_driver": ranked[0], "secondary_driver": ranked[1], "key_factors": key_factors[:5] or ["available hazard evidence"], "missing_evidence": missing}, "flood_effective_weights": flood_effective_weights, "landslide_effective_weights": landslide_effective_weights, "traffic_effective_weights": traffic_effective_weights, "config_version": config["version"], "thresholds": config["thresholds"], "accessibility_score": 100.0 * (1.0 - final_disruption),
    }


def generate_explanation(result: dict[str, Any]) -> str:
    explanation = result.get("explanation", {}) or {}
    score = float(result.get("disruption_probability", 0.0))
    factors = ", ".join(explanation.get("key_factors", [])[:3]) or "available hazard evidence"
    missing = explanation.get("missing_evidence", [])
    missing_text = f" Missing evidence: {', '.join(missing[:3])}." if missing else ""
    return f"{str(result.get('disruption_category', 'LOW')).capitalize()} disruption likelihood. Primary driver: {explanation.get('primary_driver', 'unknown')}; secondary driver: {explanation.get('secondary_driver', 'unknown')}. Key factors: {factors}. The disruption likelihood score is {score:.2f}.{missing_text}"


def compute_hybrid_engine_response(payload: dict[str, Any]) -> dict[str, Any]:
    return compute_hybrid_disruption(payload)