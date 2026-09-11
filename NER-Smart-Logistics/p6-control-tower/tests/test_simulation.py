from __future__ import annotations


def test_what_if_road_102_snapshot(client):
    r = client.post(
        "/api/v1/simulation/what-if",
        json={
            "scenario_id": "SCENARIO_001",
            "scenario_type": "ROAD_BLOCKED",
            "road_id": "ROAD_102",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["scenario_id"] == "SCENARIO_001"
    assert body["affected_roads"] == ["ROAD_102"]
    assert body["affected_shipments"] == 4
    assert body["delayed_shipments"] == 3
    assert body["affected_districts"] == 2
    assert body["additional_delay_minutes"] == 240
    assert 0 <= body["shortage_risk_change"] <= 1
    assert body["recommended_route_id"] == "ROUTE_505"
    assert body["generated_at"].endswith("Z")


def test_control_tower_overview(client):
    client.post(
        "/api/v1/incidents",
        json={
            "incident_id": "INC_1001",
            "reported_by": "DRIVER_123",
            "latitude": 27.58,
            "longitude": 91.87,
            "incident_type": "LANDSLIDE",
        },
    )
    client.post(
        "/api/v1/alerts/evaluate",
        json={
            "road_id": "ROAD_102",
            "flood_probability": 0.72,
            "landslide_probability": 0.84,
            "disruption_probability": 0.93,
            "accessibility_score": 18,
            "affected_shipments": 3,
            "critical_shipments": 2,
            "shortage_probability": 0.91,
        },
    )
    overview = client.get("/api/v1/control-tower/overview")
    assert overview.status_code == 200
    body = overview.json()
    assert body["open_incidents"] == 1
    assert body["alerts_by_severity"]["CRITICAL"] == 1
    assert "data_provenance" in body

    geo = client.get("/api/v1/control-tower/map-state")
    assert geo.status_code == 200
    fc = geo.json()
    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) == 1
    assert "ROAD_102" in fc["alert_road_ids"]
