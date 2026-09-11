import numpy as np
import pandas as pd

from p3_src.satellite_client import CDSEClient, buffer_bbox, event_windows, process_payload
from p3_src.satellite_features import extract_s1_features, extract_s2_features, predictive_features
from p3_src.satellite_pipeline import build_feasibility, eligible_events


def test_event_windows_are_explicit_and_post_event_is_separate():
    windows = event_windows("2020-01-15", event_days=1)
    assert windows["before_6_1"] == ("2020-01-09", "2020-01-14")
    assert windows["event"] == ("2020-01-14", "2020-01-16")
    assert windows["after_1_6"] == ("2020-01-16", "2020-01-21")


def test_buffer_is_approximately_250_metres():
    west, south, east, north = buffer_bbox(20.0, 75.0, 250)
    assert 0.002 < east - 75.0 < 0.003
    assert 0.002 < 20.0 - south < 0.003
    assert west < 75.0 < east and south < 20.0 < north


def test_process_payload_requests_only_experimental_bands():
    payload = process_payload("sentinel-2", (70, 10, 70.01, 10.01), "2020-01-01", "2020-01-02")
    assert payload["input"]["data"][0]["type"] == "sentinel-2-l2a"
    assert "B02" in payload["evalscript"] and "B12" in payload["evalscript"]
    assert "B01" not in payload["evalscript"]


def test_auth_configuration_and_metadata_cache(tmp_path, monkeypatch):
    monkeypatch.delenv("CDSE_CLIENT_ID", raising=False)
    monkeypatch.delenv("CDSE_CLIENT_SECRET", raising=False)
    client = CDSEClient(tmp_path)
    monkeypatch.setattr("src.satellite_client.DEFAULT_DOTENV_PATH", tmp_path / "missing.env")
    assert client.credentials_available() is False
    monkeypatch.setenv("CDSE_CLIENT_ID", "id")
    monkeypatch.setenv("CDSE_CLIENT_SECRET", "secret")
    assert client.credentials_available() is True
    calls = []
    assert client._cached_json({"query": 1}, lambda: calls.append(1) or {"value": []}) == {"value": []}
    assert client._cached_json({"query": 1}, lambda: calls.append(1) or {"value": ["unexpected"]}) == {"value": []}
    assert calls == [1]


def test_s1_and_s2_features_are_deterministic_and_handle_missing_values():
    s1 = extract_s1_features({"before": {"vv": [1, 2, np.nan], "vh": [0.5, 1]}, "event": {"vv": [3, 4], "vh": [1, 2]}})
    assert s1["s1_vv_before_mean"] == 1.5
    assert s1["s1_vv_event_change"] == 2.0
    s2 = extract_s2_features({"before": {"b03": [2, 2], "b04": [1, 1], "b08": [3, 3]}, "event": {"b03": [3, 3], "b04": [2, 2], "b08": [4, 4]}})
    assert s2["s2_ndvi_before_mean"] == 0.5
    assert "s2_ndwi_change" in s2


def test_predictive_features_exclude_post_event_values():
    values = predictive_features({"s1_vv_before_mean": 1, "s1_vv_event_mean": 2, "s1_vv_after_mean": 3, "after_marker": 4})
    assert values == {"s1_vv_before_mean": 1, "s1_vv_event_mean": 2}


def test_eligibility_rejects_missing_dates_and_coordinates():
    events = pd.DataFrame([
        {"event_id": "dated", "event_timestamp": "2020-01-01", "latitude": 20, "longitude": 75},
        {"event_id": "no-date", "event_timestamp": None, "latitude": 20, "longitude": 75},
        {"event_id": "no-coordinate", "event_timestamp": "2020-01-01", "latitude": None, "longitude": 75},
    ])
    assert eligible_events(events).event_id.tolist() == ["dated"]


def test_duplicate_products_and_feasibility_counts():
    events = pd.DataFrame([{"event_id": "e1", "event_timestamp": "2020-01-01", "latitude": 20, "longitude": 75}])
    observations = pd.DataFrame([
        {"event_id": "e1", "satellite": "sentinel-1", "product_id": "p1", "distance_days": -1, "cloud_cover": None},
        {"event_id": "e1", "satellite": "sentinel-2", "product_id": "p2", "distance_days": 3, "cloud_cover": 40},
    ]).drop_duplicates(["event_id", "satellite", "product_id"])
    result = build_feasibility(events, observations)
    assert result["events_with_sentinel_1"] == 1
    assert result["events_with_both"] == 1
    assert result["usable_within_percent"]["1"] == 100.0
    assert result["sentinel_2_cloud_affected_percent"] == 100.0
    assert result["model_status"] == "insufficient_supervised_labels"
