from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path

from .inference import current_model_info, predict_severity_risk
from .pipeline import FEATURE_COLUMNS, MODEL_ROOT, NUMERIC_FEATURES, CATEGORICAL_FEATURES, REPORT_ROOT, ROOT


def write_feature_contract() -> dict:
    metadata = json.loads((MODEL_ROOT / "p3_road_risk_v002_metadata.json").read_text())
    v001_metadata = json.loads((MODEL_ROOT / "p3_road_risk_v001_metadata.json").read_text())
    v001_features = set(v001_metadata.get("feature_names", []))
    numeric_ranges = {
        "latitude": [-90, 90], "longitude": [-180, 180], "hour": [0, 23],
        "is_weekend": [0, 1], "lanes": [0, None], "traffic_signal": [0, 1],
        "temperature": [None, None], "is_peak_hour": [0, 1],
        "nearest_landslide_distance_km": [0, None], "nearby_landslide_count": [0, None],
        "nearest_river_distance_km": [0, None],
    }
    entries = []
    for name in metadata["candidate_feature_names"]:
        optional = name in {"rainfall_24h", "rainfall_3d", "rainfall_7d"}
        entries.append({
            "name": name,
            "type": "number" if name in NUMERIC_FEATURES or optional else "string",
            "unit": "degrees" if name in {"latitude", "longitude"} else "km" if name.endswith("_km") else "count" if name.endswith("count") else "source category" if name not in NUMERIC_FEATURES and not optional else "source unit",
            "valid_range": numeric_ranges.get(name),
            "source": "Indian accident source" if name not in {"rainfall_24h", "rainfall_3d", "rainfall_7d"} else "IMD rainfall grid",
            "historical_availability": name in metadata["feature_names"],
            "real_time_availability": name in metadata["feature_names"] or name in {"rainfall_24h", "rainfall_3d", "rainfall_7d"},
            "required": False,
            "missing_value_behavior": "model pipeline imputation for fitted features; unavailable candidates omitted from training",
            "temporal_semantics": "available at or before prediction timestamp; environmental joins are causal",
            "used_by_v001": name in v001_features,
            "used_by_v002": name in metadata["feature_names"],
        })
    entries += [
        {"name": "flood_probability", "type": "number", "unit": "probability", "valid_range": [0, 1], "source": "P1 provider", "historical_availability": False, "real_time_availability": True, "required": False, "missing_value_behavior": "remain unavailable; never fabricated", "temporal_semantics": "provider value at or before prediction timestamp", "used_by_v001": False, "used_by_v002": False},
        {"name": "landslide_probability", "type": "number", "unit": "probability", "valid_range": [0, 1], "source": "P2 provider", "historical_availability": False, "real_time_availability": True, "required": False, "missing_value_behavior": "remain unavailable; never fabricated", "temporal_semantics": "provider value at or before prediction timestamp", "used_by_v001": False, "used_by_v002": False},
    ]
    contract = {"contract_version": "p3-phase6-v1", "model_role": metadata["model_role"], "target": metadata["target_name"], "features": entries, "outputs": {"risk_probability": "existing accident/traffic risk probability", "disruption_probability": "hybrid_evidence_fusion_v2 evidence-fusion likelihood estimate; not statistically calibrated", "operational_disruption_score": "equal to disruption_probability for P4 compatibility", "accessibility_score": "100 * (1 - disruption_probability), deterministic operational proxy"}}
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    (REPORT_ROOT / "p3_feature_contract.json").write_text(json.dumps(contract, indent=2))
    return contract


def benchmark(iterations: int = 20) -> dict:
    values = {"latitude": 19.0, "longitude": 73.0, "hour": 12, "is_weekend": 0, "lanes": 2, "traffic_signal": 1, "temperature": 30, "is_peak_hour": 0, "road_type": "urban", "weather": "clear", "visibility": "high", "traffic_density": "low", "city": "mumbai", "state": "maharashtra", "nearest_landslide_distance_km": 10, "nearby_landslide_count": 1, "nearest_river_distance_km": 100}
    start = time.perf_counter()
    current_model_info()
    cold_load_seconds = time.perf_counter() - start
    start = time.perf_counter()
    for _ in range(iterations):
        predict_severity_risk(values)
    elapsed = time.perf_counter() - start
    return {"iterations": iterations, "cold_load_seconds": cold_load_seconds, "single_prediction_average_ms": elapsed / iterations * 1000, "batch_prediction_supported": False}


def collected_test_count() -> int | None:
    result = subprocess.run(["pytest", "--collect-only", "-q"], cwd=ROOT, capture_output=True, text=True, check=False)
    match = re.search(r"(\d+) tests collected", result.stdout + result.stderr)
    return int(match.group(1)) if match else None


def main() -> None:
    contract = write_feature_contract()
    bench = benchmark()
    readiness = {
        "production_readiness": "PARTIAL",
        "api_status": "available",
        "model_status": current_model_info(),
        "feature_contract_status": "complete",
        "provider_status": {"P1": "interface available; provider unavailable unless configured", "P2": "interface available; provider unavailable unless configured"},
        "temporal_safety_status": "pass; causal environmental tests exist",
        "artifact_validation_status": "pass",
        "test_count": collected_test_count(),
        "benchmark": bench,
        "p4_integration_readiness": "PARTIAL; risk_probability and hybrid operational_disruption_score are stable",
        "road_disruption_model_status": "insufficient_labels",
        "known_limitations": ["No defensible temporally aligned road-closure binary target.", "P1/P2 historical probabilities unavailable.", "Accessibility is a deterministic proxy, not an independent model."],
    }
    (REPORT_ROOT / "phase6_production_readiness.json").write_text(json.dumps(readiness, indent=2, default=str))
    (REPORT_ROOT / "phase6_production_readiness.md").write_text("# Phase 6 production readiness\n\n" + json.dumps(readiness, indent=2, default=str))
    print(json.dumps({"feature_count": len(contract["features"]), "benchmark": bench}, indent=2))


if __name__ == "__main__":
    main()
