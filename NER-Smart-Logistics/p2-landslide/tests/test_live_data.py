import pytest
import requests

from app import live_data


def test_collect_live_features_keeps_other_sources_when_optional_apis_fail(monkeypatch):
    monkeypatch.setattr(live_data, "fetch_weather", lambda *_: {
        "rainfall_1h_mm": 1.0, "rainfall_6h_mm": 2.0,
        "rainfall_24h_mm": 3.0, "rainfall_7d_mm": 4.0,
        "temperature_c": 20.0, "humidity_percent": 80.0,
    })
    monkeypatch.setattr(live_data, "fetch_elevation_grid", lambda *_: [100.0] * 9)
    monkeypatch.setattr(
        live_data, "_fetch_historical_landslide_count_live",
        lambda *_: (_ for _ in ()).throw(requests.RequestException("offline")),
    )
    monkeypatch.setattr(
        live_data, "_fetch_land_cover_live",
        lambda *_: (_ for _ in ()).throw(ValueError("bad response")),
    )

    features = live_data.collect_live_features(27.5, 91.8)

    assert features["elevation_m"] == 100.0
    assert features["slope_degree"] == 0.0
    assert features["historical_landslide_count"] == 0
    assert features["land_cover"] == "grassland"
    assert features["source_status"] == {
        "weather": "live",
        "elevation": "live",
        "terrain_derivatives": "calculated_from_live_elevation",
        "historical_landslides": "fallback",
        "land_cover": "fallback",
    }


def test_collect_live_features_uses_explicit_fallbacks_for_weather_and_elevation(monkeypatch):
    monkeypatch.setattr(
        live_data, "fetch_weather",
        lambda *_: (_ for _ in ()).throw(requests.Timeout("offline")),
    )
    monkeypatch.setattr(
        live_data, "fetch_elevation_grid",
        lambda *_: (_ for _ in ()).throw(RuntimeError("offline")),
    )
    monkeypatch.setattr(live_data, "_fetch_historical_landslide_count_live", lambda *_: 2)
    monkeypatch.setattr(live_data, "_fetch_land_cover_live", lambda *_: "forest")

    features = live_data.collect_live_features(27.5, 91.8)

    assert features["rainfall_24h_mm"] == 0.0
    assert features["elevation_m"] == 0.0
    assert features["source_status"]["weather"] == "fallback"
    assert features["source_status"]["elevation"] == "fallback"
    assert features["source_status"]["terrain_derivatives"] == "fallback"
    assert features["source_status"]["historical_landslides"] == "live"


def test_overpass_request_identifies_client(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"elements": [{"tags": {"natural": "wood"}}]}

    captured = {}

    def fake_post(*args, **kwargs):
        captured.update(kwargs)
        return Response()

    monkeypatch.setattr(live_data.requests, "post", fake_post)

    assert live_data._fetch_land_cover_live(27.5, 91.8) == "forest"
    assert captured["headers"]["Accept"] == "application/json"
    assert "landslide-agent-demo" in captured["headers"]["User-Agent"]


def test_historical_fetch_rejects_missing_count(monkeypatch):
    monkeypatch.setattr(live_data, "_get", lambda *_: {"features": []})
    assert live_data.fetch_historical_landslide_count(27.5, 91.8) == 0