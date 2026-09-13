from __future__ import annotations


def test_what_if_without_p5_returns_empty(client):
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
    assert body["recommended_reroutes"] == []
    assert body["route_coordinates"] is None
    assert body["affected_shipments_detail"] == []
    assert body["generated_at"].endswith("Z")
    assert body["data_provenance"]["shipments"] == "p5_unavailable"


def test_what_if_passthrough_p5_and_p4(client, monkeypatch):
    monkeypatch.setattr(
        "simulation.clients.fetch_p5_shipments",
        lambda: [
            {
                "shipment_id": "SHIP_LIVE_1",
                "origin": "Guwahati",
                "destination": "Tawang",
                "cargo_type": "MEDICINE",
                "priority": "CRITICAL",
                "status": "ON_ROUTE",
                "estimated_arrival": "2026-09-13T12:00:00+00:00",
                "estimated_travel_time_minutes": 600,
                "route_id": "ROUTE_CURRENT",
            }
        ],
    )

    def fake_p4(origin, destination, cargo_type=None, priority=None, avoid_high_risk_roads=None):
        if avoid_high_risk_roads:
            return {
                "route_id": "ROUTE_ALT_1",
                "origin": origin,
                "destination": destination,
                "road_ids": ["NH-15", "NH-13-BYPASS"],
                "distance_km": 512.0,
                "estimated_travel_time_minutes": 860,
                "route_risk": 0.18,
                "safety_score": 82.0,
                "route_coordinates": [[26.1445, 91.7362], [27.586, 91.859]],
            }
        return {
            "route_id": "ROUTE_CURRENT",
            "origin": origin,
            "destination": destination,
            "road_ids": ["ROAD_102", "NH-13"],
            "distance_km": 480.5,
            "estimated_travel_time_minutes": 792,
            "route_risk": 0.31,
            "safety_score": 69.0,
            "route_coordinates": [[26.1445, 91.7362], [26.8, 92.1], [27.586, 91.859]],
        }

    monkeypatch.setattr("simulation.clients.request_p4_route", fake_p4)

    r = client.post(
        "/api/v1/simulation/what-if",
        json={
            "scenario_type": "ROAD_BLOCKED",
            "road_id": "ROAD_102",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["affected_shipments"] == 1
    assert body["delayed_shipments"] == 1
    assert body["affected_districts"] == 1
    assert body["recommended_route_id"] == "ROUTE_ALT_1"
    assert body["additional_delay_minutes"] == 68
    assert body["shortage_risk_change"] is None
    assert body["route_coordinates"] == [[26.1445, 91.7362], [27.586, 91.859]]
    assert body["affected_shipments_detail"][0]["shipment_id"] == "SHIP_LIVE_1"
    assert body["recommended_reroutes"][0]["distance_km"] == 512.0
    assert body["recommended_reroutes"][0]["route_risk"] == 0.18
    assert body["data_provenance"]["shipments"] == "p5_http_live"


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
