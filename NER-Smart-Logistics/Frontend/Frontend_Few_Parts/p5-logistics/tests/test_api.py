from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


def test_health():
    r = client.get('/health')
    assert r.status_code == 200
    assert r.json()['status'] == 'ok'


def test_shipment():
    payload = {
        'shipment_id': 'SHIP_1001', 'origin': 'Guwahati', 'destination': 'Tawang',
        'cargo_type': 'MEDICINE', 'quantity': 500, 'unit': 'BOX', 'priority': 'CRITICAL',
        'requested_delivery': '2026-09-05T12:00:00Z',
        'route': {'route_id': 'ROUTE_501', 'estimated_travel_time_minutes': 792, 'route_risk': 0.21}
    }
    r = client.post('/api/v1/shipments', json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body['shipment_id'] == 'SHIP_1001'
    assert 0 <= body['shipment_risk'] <= 1


def test_shortage():
    payload = {
        'district_id': 'DIST_001', 'district_name': 'Tawang', 'product_type': 'MEDICINE',
        'current_inventory_units': 450, 'average_daily_consumption': 150,
        'incoming_quantity_units': 500, 'incoming_eta_days': 4.0,
        'road_risk': 0.82, 'population': 55000
    }
    r = client.post('/api/v1/predictions/shortage', json=payload)
    assert r.status_code == 200
    body = r.json()
    assert 0 <= body['shortage_probability'] <= 1
    assert body['model_version'] == 'shortage_baseline_v1'


def test_warehouse_optimization():
    payload = {
        'product_type': 'MEDICINE',
        'warehouses': [
            {'warehouse_id': 'WH_001', 'location': 'Guwahati', 'available_units': 5000},
            {'warehouse_id': 'WH_002', 'location': 'Tezpur', 'available_units': 1800}
        ],
        'target_districts': [
            {'district_id': 'DIST_001', 'demand_units': 1000, 'shortage_probability': 0.91}
        ]
    }
    r = client.post('/api/v1/warehouses/optimize', json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body['optimization_status'] == 'OPTIMAL'
    assert sum(x['recommended_quantity'] for x in body['recommendations']) == 1000
