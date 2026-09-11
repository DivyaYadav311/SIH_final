# NER Smart Logistics — P5 Deliverable

Standalone implementation for **Person 5 — Logistics & Supply Chain**.

Includes:
- Shipment management + critical shipment prioritization
- Supply shortage prediction baseline
- Warehouse allocation optimization
- REST API contracts ready for P4/P6 integration
- Temporary dependency-free frontend for verification

## Start backend
```bash
cd p5-logistics
python -m venv .venv
# Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn src.main:app --reload --port 8000
```

## Start frontend in another terminal
```bash
cd frontend
python -m http.server 5500
```

Open `http://localhost:5500`.
