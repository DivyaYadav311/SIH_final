# Integration Guide

### P4 → P5
P4 owns route computation. Send its live result into `POST /api/v1/shipments` under `route`:
- `route_id`
- `estimated_travel_time_minutes`
- `route_risk`

### P5 → P6
P6 can call:
- `GET /api/v1/shipments`
- `POST /api/v1/predictions/shortage`
- `POST /api/v1/warehouses/optimize`

### P3/P1/P2 influence
P5 should not duplicate flood, landslide or road-risk models. Consume their normalized outputs through P4 or shared schemas.
