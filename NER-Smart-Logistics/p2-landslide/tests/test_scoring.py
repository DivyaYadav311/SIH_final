from app import scoring


def test_fallback_risk_engine_is_explicit_heuristic(monkeypatch):
    monkeypatch.setattr(scoring, "MODEL_PATH", "missing-model.pkl")
    monkeypatch.setattr(scoring, "_trained_model", None)
    monkeypatch.setattr(scoring, "_trained_model_load_attempted", False)
    features = {
        "rainfall_1h_mm": 0.0, "rainfall_6h_mm": 0.0,
        "rainfall_24h_mm": 0.0, "rainfall_7d_mm": 0.0,
        "temperature_c": 20.0, "humidity_percent": 50.0,
        "elevation_m": 100.0, "slope_degree": 0.0, "aspect_degree": 0.0,
        "land_cover": "grassland", "historical_landslide_count": 0,
    }
    probability, risk, confidence, model_version = scoring.predict_landslide_risk(features)
    assert 0.0 <= probability <= 1.0
    assert risk == "LOW"
    assert 0.55 <= confidence <= 0.99
    assert model_version == "landslide_heuristic_v0"
