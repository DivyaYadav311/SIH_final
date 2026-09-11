from fastapi.testclient import TestClient

from app.main import app
from app import main


FEATURES = {
    "rainfall_1h_mm": 1.0, "rainfall_6h_mm": 2.0,
    "rainfall_24h_mm": 3.0, "rainfall_7d_mm": 4.0,
    "temperature_c": 20.0, "humidity_percent": 80.0,
    "elevation_m": 100.0, "slope_degree": 12.0, "aspect_degree": 180.0,
    "land_cover": "forest", "historical_landslide_count": 1,
    "source_status": {"weather": "live", "elevation": "live",
                       "terrain_derivatives": "calculated_from_live_elevation",
                       "historical_landslides": "fallback", "land_cover": "live"},
}


def test_health_endpoint():
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "mode": "live-api"}


def test_live_features_endpoint_reports_provenance(monkeypatch):
    monkeypatch.setattr(main, "collect_live_features", lambda *_: FEATURES.copy())
    response = TestClient(app).get("/api/v1/live-features?latitude=27.5&longitude=91.8")
    body = response.json()

    assert response.status_code == 200
    assert body["features"]["elevation_m"] == 100.0
    assert body["source_status"]["historical_landslides"] == "fallback"
    assert "source_status" not in body["features"]


def test_prediction_endpoint_uses_live_features(monkeypatch):
    monkeypatch.setattr(main, "collect_live_features", lambda *_: FEATURES.copy())
    response = TestClient(app).post(
        "/api/v1/predictions/landslide",
        json={"location_id": "LOC_001", "latitude": 27.5, "longitude": 91.8},
    )
    body = response.json()

    assert response.status_code == 200
    assert body["model_version"] in {"landslide_heuristic_v0", "landslide_logistic_regression_v1"}
    assert 0.0 <= body["landslide_probability"] <= 1.0
    assert body["live_features"]["land_cover"] == "forest"


def test_prediction_returns_502_for_unexpected_required_pipeline_failure(monkeypatch):
    monkeypatch.setattr(main, "collect_live_features", lambda *_: (_ for _ in ()).throw(RuntimeError("broken")))
    response = TestClient(app).post(
        "/api/v1/predictions/landslide",
        json={"latitude": 27.5, "longitude": 91.8},
    )
    assert response.status_code == 502
