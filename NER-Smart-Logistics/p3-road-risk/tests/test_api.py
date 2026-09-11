from fastapi.testclient import TestClient
from p3_src.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/api/v1/road-risk/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "road-risk-engine",
        "risk_model_status": "available",
        "road_disruption_model_status": "insufficient_labels",
    }

def test_model_info_distinguishes_accident_risk_from_disruption():
    response = client.get("/api/v1/road-risk/model")
    assert response.status_code == 200
    payload = response.json()
    assert payload["model_version"] == "p3_road_risk_v002"
    assert payload["target"] == "severity_risk_target"
    assert payload["road_disruption_model_status"] == "insufficient_labels"

def test_analyze_endpoint():
    payload = {
        "request_id": "REQ-001",
        "timestamp": "2026-09-04T10:30:00Z",
        "roads": [
            {
                "road_id": "ROAD-001",
                "road_class": "primary",
                "lanes": 2,
                "surface": "asphalt"
            },
            {
                "road_id": "ROAD-002",
                "road_class": "unclassified",
                "lanes": 1,
                "surface": "dirt"
            }
        ],
        "hazard_context": [
            {
                "road_id": "ROAD-001",
                "flood_probability": 0.82,
                "landslide_probability": 0.15
            },
            {
                "road_id": "ROAD-002",
                "flood_probability": 0.10,
                "landslide_probability": 0.95
            }
        ],
        "incidents": [
            {
                "incident_id": "INC-1001",
                "road_id": "ROAD-001",
                "type": "waterlogging",
                "severity": 4,
                "status": "active",
                "latitude": 19.0761,
                "longitude": 72.8780,
                "reported_at": "2026-09-04T10:15:00Z"
            }
        ]
    }
    
    response = client.post("/api/v1/road-risk/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["request_id"] == "REQ-001"
    assert len(data["roads"]) == 2
    
    road1 = next(r for r in data["roads"] if r["road_id"] == "ROAD-001")
    assert road1["disruption_probability"] > 0.5
    assert road1["risk_level"] in ["high", "critical"]
    assert road1["factors"]["active_incident_count"] == 1
    assert "High flood probability" in str(road1["explanation"])

    road2 = next(r for r in data["roads"] if r["road_id"] == "ROAD-002")
    assert road2["disruption_probability"] > 0.5
    assert road2["risk_level"] in ["high", "critical"]
    assert road2["factors"]["active_incident_count"] == 0
    assert "High landslide probability" in str(road2["explanation"])

def test_predict_endpoint_accepts_optional_upstream_probabilities():
    response = client.post("/api/v1/road-risk/predict", json={
        "road_id": "ROAD-ML-001",
        "latitude": 19.076,
        "longitude": 72.878,
        "timestamp": "2026-09-05T12:00:00Z",
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
        "flood_probability": 0.72,
        "landslide_probability": 0.18,
    })
    assert response.status_code == 200
    payload = response.json()
    assert payload["road_id"] == "ROAD-ML-001"
    assert 0 <= payload["risk_probability"] <= 1
    assert 0 <= payload["operational_disruption_score"] <= 1
    assert 0 <= payload["disruption_probability"] <= 1
    assert 0 <= payload["accessibility_score"] <= 100
    assert abs(sum(payload["score_contributions"].values()) - payload["operational_disruption_score"]) < 1e-9
    assert payload["model_version"] == "p3_road_risk_v002"
    assert payload["road_disruption_model_status"] == "insufficient_labels"
    assert payload["explanation"]["primary_driver"] in {"flood", "landslide", "traffic"}
    assert payload["factors"]["flood_probability"] == 0.72
    assert payload["evidence"]["flood"] is True

def test_predict_rejects_invalid_numeric_inputs():
    payload = {"road_id": "ROAD", "latitude": 19.0, "longitude": 73.0, "timestamp": "2026-09-05T12:00:00Z", "flood_probability": 1.1}
    assert client.post("/api/v1/road-risk/predict", json=payload).status_code == 422
    payload["flood_probability"] = "NaN"
    assert client.post("/api/v1/road-risk/predict", json=payload).status_code == 422

def test_predict_is_deterministic_and_accessibility_boundaries_are_valid():
    payload = {"road_id": "ROAD", "latitude": 19.0, "longitude": 73.0, "timestamp": "2026-09-05T12:00:00Z"}
    first = client.post("/api/v1/road-risk/predict", json=payload)
    second = client.post("/api/v1/road-risk/predict", json=payload)
    assert first.json() == second.json()
    assert 0 <= first.json()["accessibility_score"] <= 100
