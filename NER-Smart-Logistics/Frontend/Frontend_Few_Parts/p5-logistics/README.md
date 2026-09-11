# P5 — Logistics & Supply Chain

FastAPI MVP for the NER Smart Logistics SIH 26002 module.

## Responsibilities
- Shipment management and risk scoring
- Critical shipment prioritization through `priority`
- Explainable supply-shortage prediction baseline
- Warehouse allocation / optimization
- Clean API contracts for integration with P4 routing and P6 control tower

## Run
From `p5-logistics/`:

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
uvicorn src.main:app --reload --port 8000
```

Open `http://localhost:8000/docs` for Swagger.

## Tests
```bash
pytest -q
```

## Integration contract
P4 should send `route_id`, `estimated_travel_time_minutes`, and `route_risk` into the shipment endpoint. P3/P4 can update these values from their live flood/landslide/accessibility outputs. P6 can consume shipment, shortage, and optimization outputs.

The shortage endpoint currently uses an explainable baseline model so the MVP works immediately. A trained XGBoost model can later be loaded from `models/` without changing the endpoint contract.
