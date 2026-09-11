from __future__ import annotations

from alerts.engine import evaluate_severity
from p6_src.schemas import AlertEvaluateIn


def test_evaluate_critical_reroute(client):
    payload = {
        "road_id": "ROAD_102",
        "flood_probability": 0.72,
        "landslide_probability": 0.84,
        "disruption_probability": 0.93,
        "accessibility_score": 18,
        "affected_shipments": 3,
        "critical_shipments": 2,
        "shortage_probability": 0.91,
        "affected_districts": ["Tawang"],
    }
    r = client.post("/api/v1/alerts/evaluate", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["alert_id"].startswith("ALERT_")
    assert body["severity"] == "CRITICAL"
    assert body["recommended_action"] == "REROUTE"
    assert body["title"] == "Critical road disruption"
    assert body["affected_road"] == "ROAD_102"
    assert body["affected_shipments"] == 3
    assert body["affected_districts"] == ["Tawang"]
    assert body["generated_at"].endswith("Z")

    listed = client.get("/api/v1/alerts")
    assert len(listed.json()) == 1


def test_evaluate_low_monitor():
    inp = AlertEvaluateIn(
        road_id="ROAD_001",
        flood_probability=0.05,
        landslide_probability=0.04,
        disruption_probability=0.10,
        accessibility_score=90,
        affected_shipments=0,
        critical_shipments=0,
        shortage_probability=0.05,
    )
    severity, action, _title = evaluate_severity(inp)
    assert severity == "LOW"
    assert action == "MONITOR"


def test_evaluate_high_reroute():
    inp = AlertEvaluateIn(
        road_id="ROAD_002",
        flood_probability=0.4,
        landslide_probability=0.4,
        disruption_probability=0.62,
        accessibility_score=50,
        affected_shipments=1,
        critical_shipments=0,
        shortage_probability=0.2,
    )
    severity, action, _title = evaluate_severity(inp)
    assert severity == "HIGH"
    assert action == "REROUTE"
