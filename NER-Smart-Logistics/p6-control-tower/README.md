# NER Smart Logistics — P6 Control Tower

Independent FastAPI module for **driver reporting**, **incident management**, **image verification**, **real-time alerts**, **what-if simulation**, and **control-tower aggregation**.

Does not import P1–P5 Python packages. Upstream services are optional HTTP (`P3_BASE_URL`, `P4_BASE_URL`, `P5_BASE_URL`). Official IMD CAP warnings are fetched from IMD WIS2.

## Run (Windows)

```text
cd p6-control-tower
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn p6_src.main:app --reload --host 127.0.0.1 --port 8006
```

Open the test dashboard at `http://127.0.0.1:8006/dashboard` (or `frontend-test/index.html` in a browser; CORS is already enabled).

Local CLIP fallback also needs `torch` (install from [pytorch.org](https://pytorch.org) for your platform). If `HF_TOKEN` is set, classification uses the Hugging Face Inference API and does not require a local GPU.

```text
pytest
```

## Environment

See `.env.example` in this folder and the repo-root `.env.example`.

| Variable | Required | Role |
|---|---|---|
| `DATABASE_URL` | no | Default: SQLite at `data/p6.db` |
| `HF_TOKEN` | no | Hugging Face Inference API for CLIP |
| `P3_BASE_URL` | no | Future road-risk service |
| `P4_BASE_URL` | no | Route optimize for what-if alternatives |
| `P5_BASE_URL` | no | Live shipments for simulation |
| `IMD_CAP_MESSAGES_URL` | no | Default IMD WIS2 messages collection |

## APIs

| Method | Path |
|---|---|
| GET | `/health` |
| GET | `/api/v1/data-sources` |
| POST | `/api/v1/incidents` |
| GET | `/api/v1/incidents` |
| GET | `/api/v1/incidents/{incident_id}` |
| PATCH | `/api/v1/incidents/{incident_id}` |
| POST | `/api/v1/incidents/{incident_id}/verify` |
| POST | `/api/v1/alerts/evaluate` |
| GET | `/api/v1/alerts` |
| GET | `/api/v1/alerts/imd` |
| WS | `/ws/alerts` |
| POST | `/api/v1/simulation/what-if` |
| GET | `/api/v1/control-tower/overview` |
| GET | `/api/v1/control-tower/map-state` |

Full JSON examples: [docs/api-contracts.md](../docs/api-contracts.md).

## Image verification

1. Download `image_url`.
2. Read EXIF GPS and compare to reported coordinates (mismatch if farther than `P6_EXIF_MISMATCH_KM`, default 5 km). EXIF never invents `detected_type`.
3. Classify with CLIP labels `LANDSLIDE | FLOOD | ROAD_BLOCKED | ACCIDENT | CLEAR`:
   - `huggingface_api` when `HF_TOKEN` is set
   - else `local_clip` via `transformers`

## Snapshots

`data/snapshots/` holds schema-faithful P4/P5-shaped records so what-if works before those services exist. They are not a fake IMD or OSM substitute. Prefer HTTP when `P4_BASE_URL` / `P5_BASE_URL` are set.

## Database

SQLAlchemy creates P6 tables on startup. Canonical DDL: [shared/database/p6_tables.sql](../shared/database/p6_tables.sql).
