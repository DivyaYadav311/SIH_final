from fastapi.testclient import TestClient

from p5_src.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")

    assert r.status_code == 200

    body = r.json()

    assert body["status"] == "ok"


def test_shipment():
    payload = {
        "shipment_id": "SHIP_TEST_1001",
        "origin": "Guwahati",
        "destination": "Tawang",
        "cargo_type": "MEDICINE",
        "quantity": 500,
        "unit": "BOX",
        "priority": "CRITICAL",
        "requested_delivery": "2026-09-10T12:00:00Z",
    }

    r = client.post(
        "/api/v1/shipments",
        json=payload,
    )

    assert r.status_code == 200

    body = r.json()

    assert body["shipment_id"] == "SHIP_TEST_1001"
    assert body["route_id"] is not None

    assert 0 <= body["shipment_risk"] <= 1
    assert 0 <= body["route_risk"] <= 1

    assert body["status"] == "PLANNED"


def test_shortage():
    payload = {
        "district_id": "DIST_001",
        "district_name": "Tawang",

        # P5 needs an origin to obtain route information
        # from P4 in the future route-aware shortage flow.
        "origin": "Guwahati",

        "product_type": "MEDICINE",
        "priority": "CRITICAL",

        "current_inventory_units": 450,
        "average_daily_consumption": 150,

        "incoming_quantity_units": 500,
        "incoming_eta_days": 4.0,

        "population": 55000,
    }

    r = client.post(
        "/api/v1/predictions/shortage",
        json=payload,
    )

    assert r.status_code == 200

    body = r.json()

    assert 0 <= body["shortage_probability"] <= 1

    assert body["model_version"] == "shortage_baseline_v1"

    assert body["district_id"] == "DIST_001"
    assert body["product_type"] == "MEDICINE"


def test_warehouse_optimization():
    payload = {
        "product_type": "MEDICINE",

        "target_districts": [
            {
                "district_id": "DIST_001",
                "demand_units": 500,
                "shortage_probability": 0.91,
            }
        ],
    }

    r = client.post(
        "/api/v1/warehouses/optimize",
        json=payload,
    )

    assert r.status_code == 200

    body = r.json()

    assert body["optimization_status"] in [
        "OPTIMAL",
        "FEASIBLE",
        "NO_FEASIBLE_ALLOCATION",
    ]

    total_allocated = sum(
        item["recommended_quantity"]
        for item in body["recommendations"]
    )

    assert total_allocated <= 500

    for recommendation in body["recommendations"]:
        assert recommendation["product_type"] == "MEDICINE"
        assert recommendation["recommended_quantity"] > 0
        assert recommendation["from_warehouse"].startswith("WH_")
        assert recommendation["to_location"] == "DIST_001"

def test_demand_prediction():
    payload = {
        "district_id": "DIST_001",
        "district_name": "Tawang",
        "product_type": "MEDICINE",
        "historical_daily_demand": [
            120,
            130,
            125,
            140,
            145,
            150,
            160
        ],
        "forecast_days": 7,
    }

    r = client.post(
        "/api/v1/predictions/demand",
        json=payload
    )

    assert r.status_code == 200

    body = r.json()

    assert body["district_id"] == "DIST_001"
    assert body["product_type"] == "MEDICINE"

    assert body["predicted_daily_demand"] > 0
    assert body["predicted_total_demand"] > 0

    assert 0 <= body["confidence"] <= 1

    assert (
        body["model_version"]
        == "demand_weighted_moving_average_v1"
    )

def test_shortage_with_demand_forecast():
    payload = {
        "district_id": "DIST_001",
        "district_name": "Tawang",
        "origin": "Guwahati",
        "product_type": "MEDICINE",
        "priority": "CRITICAL",

        "current_inventory_units": 450,
        "average_daily_consumption": 150,

        "historical_daily_demand": [
            120,
            130,
            125,
            140,
            145,
            150,
            160,
        ],

        "incoming_quantity_units": 500,
        "incoming_eta_days": 4.0,
        "population": 55000,
    }

    r = client.post(
        "/api/v1/predictions/shortage",
        json=payload,
    )

    assert r.status_code == 200

    body = r.json()

    assert body["district_id"] == "DIST_001"
    assert body["product_type"] == "MEDICINE"

    assert 0 <= body["shortage_probability"] <= 1

    assert body["estimated_days_until_shortage"] > 0

    assert body["risk_level"] in [
        "LOW",
        "MEDIUM",
        "HIGH",
        "CRITICAL",
    ]

    assert 0 <= body["confidence"] <= 1

    assert body["model_version"] == (
        "shortage_demand_route_v1"
    )

    # P4 integration should populate route information
    # when P4 is available.
    assert body["route_id"] is not None





