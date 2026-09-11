from pathlib import Path

import pandas as pd

from p3_src.ml_pipeline import pipeline


def test_coordinate_validation_and_target_mapping():
    frame = pd.DataFrame(
        {
            "date": ["2024-01-01", "bad"],
            "time": ["10:00", "11:00"],
            "latitude": [20.0, 200.0],
            "longitude": [78.0, 78.0],
            "accident_severity": ["fatal", "minor"],
        }
    )
    for column in ["hour", "is_weekend", "lanes", "traffic_signal", "temperature", "vehicles_involved", "casualties", "is_peak_hour"]:
        frame[column] = 1
    for column in ["road_type", "weather", "visibility", "traffic_density", "cause", "city", "state"]:
        frame[column] = "unknown"
    frame["source_dataset"] = "test"
    frame["source_file"] = "test"
    frame["source_row_id"] = "row"
    frame["risk_score"] = 0.5
    cleaned = pipeline.clean_accidents(frame)
    assert len(cleaned) == 1
    assert cleaned.iloc[0][pipeline.TARGET] == 1
    assert cleaned.iloc[0]["latitude"] == 20.0


def test_chronological_split_has_no_overlap():
    frame = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=20, freq="D"),
            pipeline.TARGET: [0, 1] * 10,
        }
    )
    parts = pipeline.split_data(frame)
    assert parts["train"].timestamp.max() < parts["validation"].timestamp.min()
    assert parts["validation"].timestamp.max() < parts["test"].timestamp.min()
    assert set(parts["train"].index).isdisjoint(parts["test"].index)


def test_environmental_window_never_uses_future_observation():
    times = pd.DatetimeIndex(["2025-01-01", "2025-01-03", "2025-01-05"])
    assert pipeline._causal_window_bounds(times, pd.Timestamp("2025-01-04"), 1) == (1, 1)
    assert pipeline._causal_window_bounds(times, pd.Timestamp("2024-12-31"), 1) is None


def test_leakage_audit_rejects_target_derived_column(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "REPORT_ROOT", tmp_path)
    frame = pd.DataFrame({pipeline.TARGET: [0, 1], "risk_score": [0.1, 0.9]})
    try:
        pipeline.leakage_audit(frame)
    except ValueError:
        pass
    else:
        raise AssertionError("target-derived risk_score must fail the leakage audit")


def test_checkpoint_reuses_matching_input_and_invalidates_changed_input(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "CHECKPOINT_ROOT", tmp_path)
    calls = []

    def build():
        calls.append(1)
        return pd.DataFrame({"value": [len(calls)]})

    output = tmp_path / "stage" / "out.parquet"
    first = pipeline.checkpoint("stage", "hash-a", {"x": 1}, output, build)
    second = pipeline.checkpoint("stage", "hash-a", {"x": 1}, output, build)
    third = pipeline.checkpoint("stage", "hash-b", {"x": 1}, output, build)
    assert first.iloc[0]["value"] == 1
    assert second.iloc[0]["value"] == 1
    assert third.iloc[0]["value"] == 2
    assert len(calls) == 2


def test_trained_model_probability_and_optional_upstream_contract():
    current = pipeline.MODEL_ROOT / "current_model.json"
    if not current.exists():
        return
    from p3_src.ml_pipeline.inference import predict_severity_risk

    result = predict_severity_risk(
        {
            "latitude": 19.0,
            "longitude": 73.0,
            "hour": 12,
            "is_weekend": 0,
            "lanes": 2,
            "traffic_signal": 1,
            "temperature": 30,
            "vehicles_involved": 2,
            "casualties": 1,
            "is_peak_hour": 0,
            "road_type": "urban",
            "weather": "clear",
            "visibility": "high",
            "traffic_density": "low",
            "cause": "weather",
            "city": "mumbai",
            "state": "maharashtra",
            "flood_probability": 0.7,
            "landslide_probability": 0.2,
        }
    )
    assert 0.0 <= result["risk_probability"] <= 1.0
    assert 0.0 <= result["disruption_probability"] <= 1.0
    assert result["operational_disruption_score"] == result["disruption_probability"]
    assert result["disruption_method"] == "hybrid_evidence_fusion_v2"
    assert 0.0 <= result["accessibility_score"] <= 100.0


def test_rainfall_join_never_uses_future_observations(tmp_path, monkeypatch):
    rainfall = pd.DataFrame({"timestamp": pd.to_datetime(["2025-01-02"]), "latitude": [20.0], "longitude": [78.0]})
    monkeypatch.setattr(pipeline, "RAINFALL_NETCDF", tmp_path / "missing.nc")
    monkeypatch.setattr(pipeline, "REPORT_ROOT", tmp_path / "reports")
    result = pipeline._add_rainfall_features(rainfall)
    assert result["rainfall_24h"].isna().all()
    assert pipeline.json.loads((pipeline.REPORT_ROOT / "rainfall_enrichment_report.json").read_text())["future_values_used"] == 0
