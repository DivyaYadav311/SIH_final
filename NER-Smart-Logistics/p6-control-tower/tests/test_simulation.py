from __future__ import annotations


def test_what_if_without_live_p5_data_returns_empty_state(client):
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
    assert body["affected_shipments"] == 0
    assert body["delayed_shipments"] == 0
    assert body["affected_districts"] == 0
    assert body["additional_delay_minutes"] is None
    assert body["shortage_risk_change"] is None
    assert body["recommended_route_id"] is None
    assert body["recommended_route"] is None
    assert body["route_geometry"] is None
    assert body["affected_shipment_records"] == []
    assert set(body["unavailable_metrics"]) == {
        "additional_delay_minutes",
        "recommended_route",
        "route_geometry",
        "shipments",
    }
    assert body["data_provenance"]["shipments"] == "unavailable"
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
    assert body["shipments_monitored"] == 0
    assert "data_provenance" in body

    geo = client.get("/api/v1/control-tower/map-state")
    assert geo.status_code == 200
    fc = geo.json()
    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) == 1
    assert "ROAD_102" in fc["alert_road_ids"]
