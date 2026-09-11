from __future__ import annotations

import re

ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["module"] == "p6-control-tower"


def test_data_sources(client):
    r = client.get("/api/v1/data-sources")
    assert r.status_code == 200
    assert "IMD CAP" in r.json()["sources"]


def test_create_incident_under_verification(client):
    payload = {
        "incident_id": "INC_1001",
        "reported_by": "DRIVER_123",
        "latitude": 27.58,
        "longitude": 91.87,
        "incident_type": "LANDSLIDE",
        "description": "Road blocked by debris",
        "timestamp": "2026-09-03T15:20:00Z",
    }
    r = client.post("/api/v1/incidents", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["incident_id"] == "INC_1001"
    assert body["status"] == "UNDER_VERIFICATION"
    assert body["detected_type"] is None
    assert ISO.match(body["timestamp"])

    listed = client.get("/api/v1/incidents", params={"status": "UNDER_VERIFICATION"})
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    got = client.get("/api/v1/incidents/INC_1001")
    assert got.json()["incident_type"] == "LANDSLIDE"

    patched = client.patch("/api/v1/incidents/INC_1001", json={"status": "VERIFIED"})
    assert patched.json()["status"] == "VERIFIED"


def test_incident_auto_id(client):
    r = client.post(
        "/api/v1/incidents",
        json={
            "reported_by": "DRIVER_9",
            "latitude": 26.14,
            "longitude": 91.73,
            "incident_type": "FLOOD",
        },
    )
    assert r.status_code == 200
    assert r.json()["incident_id"].startswith("INC_")
    assert ISO.match(r.json()["timestamp"])
