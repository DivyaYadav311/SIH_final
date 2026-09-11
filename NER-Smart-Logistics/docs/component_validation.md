# Component Validation Report

This validation report is written from the repository’s existing check-in artifacts and the actual terminal evidence collected in the current workspace. No model training, dataset download, external API call, or model fabrication was performed.

| Component | Import | Model Load | Inference | API | Tests | Status |
|---|---|---|---|---|---|---|
| P1 Flood | PASS — `pytest -q` in `p1-flood` imported and executed the flood-score tests from the repository without a collection error. | PARTIAL — Proof of an optional trained artifact exists in the docs and model path, but no forced artifact load was required for this validation. | PASS — Small inference can be exercised by `compute_flood_probability` from `src/flood_score.py` without touching external APIs. | No service API entrypoint required by the core flood scoring module. | PASS — `7 passed` from `p1-flood/tests/test_flood_score.py` using `pytest -q`. | PARTIALLY_WORKING |
| P2 Landslide | FAIL — `pytest -q` in `p2-landslide` fails at collection with `ModuleNotFoundError: No module named 'app'`, meaning the package import root is not available from the checked-in test execution context. | PARTIAL — `MODEL_PATH` and `MODEL_VERSION` are optional environment variables and the scoring fallback is explicit. No trained artifact was loaded. | BLOCKED — The smallest inference path in the landslide workspace is currently blocked by the missing import-root resolution. | FAIL — `uvicorn app.main:app` is declared in README, but the repo tests cannot import `app.main` without the correct Python path set. | FAIL — Collection errors for `test_api.py`, `test_live_data.py`, `test_model_status.py`, `test_scoring.py`, `test_training.py` all fail before execution. | BROKEN |
| P3 Road Risk | PASS — `pytest -q` in `p3-road-risk` passed all tests with a 94/94 count and no collection import failures. | PASS — The code references the tracked `models/current_model.json` and optional model metadata; the service’s test suite was not blocked by missing artifact path handling. | PASS — Inference wiring is validated through the Pydantic request and response path in the tests without external APIs. | PASS — `src/api.py` exposes `GET /health`, `GET /model`, `POST /predict`, and `POST /analyze`. | PASS — `94 passed`. | WORKING_WITH_CONFIG |
| P4 Routing | PASS — `pytest -q` in `p4-path-optimization` passed all 9 tests. | NOT APPLICABLE — No model artifact is the active route scoring authority. The system is deterministic and rule-based. | PASS — The route optimizer test suite validates the route data path and the risk/scoring functions. | PASS — `GET /health`, `GET /api/v1/data-sources`, `GET /api/v1/alerts/imd`, and `POST /api/v1/routes/optimize` are exposed through the route app. | PASS — `9 passed`. | WORKING |
| P5 Logistics | FAIL — `pytest -q` in `p5-logistics` fails at collection with `ModuleNotFoundError: No module named 'src'`, meaning the local `src` package is not importable from the test command. | NOT APPLICABLE — No active trained model artifact is required by the existing shipping baseline. The service uses P4 integration and a local explainable shortage baseline. | BLOCKED — The API path shows route integration via `P4_BASE_URL` but no actual internal route server was started. | PASS in structure only — `P4RouteClient` and route integration endpoints exist in code; run-time route source requires a configured `P4_BASE_URL`. | FAIL — `1 error during collection` in `test_api.py`. | BROKEN |
| P6 Control Tower | PASS — tests import and run successfully from `p6-control-tower`. | NOT APPLICABLE — It uses CLIP as optional inference, and the model is a remote/local selection rather than a trained artifact in the project. | PASS — The test suite and service configuration use snapshot fallback and local CLIP/remote API branch. | PASS — `GET /health`, `GET /api/v1/data-sources`, incidents endpoints, alerts endpoint, and simulation endpoints exist. | PASS — `13 passed`. | WORKING_WITH_CONFIG |

## Validation Notes

### P1

- Import: OK.
- Model artifact: Optional artifact is documented in `p1-flood/src/flood_score.py` and `src/ml_model.py`. Not forced for the test suite.
- Inference: The unit test directly exercises `compute_flood_probability` and verifies monotonicity and score bounds.
- API: No synthetic API or remote call used. This is a direct scoring module.
- Test evidence: `7 passed in 4.07s`.
- Failure evidence: No failure from the repository tests. Warning: `scikit-learn` sees a mismatched NumPy/SciPy stack but the tests still executed.

### P2

- Import: FAIL — tests cannot import `app` because this workspace is missing a `PYTHONPATH` or package setup for P2. It is not enough to try `pytest` from the component folder alone.
- Model artifact: Optional `MODEL_PATH` and environment model version fields exist; no artifact is loaded from the test path.
- Inference: The explicit scoping of model fallback is in the scoring code, but inference cannot be asserted in the workspace due the import error.
- API: `app.main` route structure is present; `GET /api/v1/live-features` and `POST /api/v1/predictions/landslide` are visible in `src` docs, but a live request cannot be made without import resolution.
- Failure evidence: `ModuleNotFoundError: No module named 'app'` on every test collection.

### P3

- Import: OK.
- Model load: Optional `current_model.json` and `models/p3_road_risk_v002.joblib` present. The service’s API and tests validate the model contract without forcing an external network call.
- Inference: `POST /predict` route and `predict_severity_risk` path exercised by tests. No numerical out-of-range faults were seen in the test suite.
- API: `GET /health`, `GET /model`, `POST /predict`, `POST /analyze` are implemented; `GET /roads/{road_id}` is stated as a `501` stub and returns not implemented.
- Test evidence: `94 passed in 34.71s`.
- Key evidence: The optional geospatial satellite flow requires `CDSE_CLIENT_ID` and `CDSE_CLIENT_SECRET` in the P3 environment file; the code does not print them in its outputs and the `.env` in the folder contains the secret-shaped values. This report does not disclose them.

### P4

- Import: OK.
- Model artifact: Not applicable; `src.router` and `src.risk_engine` implement deterministic scoring.
- Inference: Route optimization code and test `test_router.py` cover route and graph examples.
- API: route health, data-sources and route optimizer endpoints exist, with corresponding route event enrichment.
- Test evidence: `9 passed`.

### P5

- Import: FAIL — service tests cannot discover `src` as a Python package when running tests from the component’s folder.
- Model artifact: The baseline shortage model is explainable, local, and built from the Python code’s own data structures; no separate joblib artifact is needed.
- Inference: The service responds through `P4RouteClient` to route information but is not testable without the route client import path and route service base URL.
- API: `P4_BASE_URL` is an environment variable; tests do not reach a real P4 service, so they fail at import time.
- Failure evidence: `ModuleNotFoundError: No module named 'src'`.

### P6

- Import: OK.
- Model artifact: CLIP is loaded from `HF_CLIP_MODEL` or from optional local `transformers`; the model is not a repository artifact.
- Inference: CLIP label verification and optional HF inference API branch are in code. If `HF_TOKEN` is set, classification hits the Hugging Face inference API; otherwise the local CLIP fallback path is used.
- API: `src.main` and route configuration expose the APIs described in the component README.
- Test evidence: `13 passed`.
- Key evidence: `HF_TOKEN` or `HUGGINGFACEHUB_API_TOKEN` is optional. No forced failure occurs when token is absent.

## Required API key inventory from the validation run

This repository exposes the following key-like requirements in the checked-in codebase:

- `CDSE_CLIENT_ID` and `CDSE_CLIENT_SECRET` in P3; required by the optional Copernicus Data Space satellite pipeline.
- `HF_TOKEN` or `HUGGINGFACEHUB_API_TOKEN` in P6; needed for the Hugging Face Inference API route in the CLIP verification branch.
- `INDIAN_RAIL_API_KEY` in P4 optional route service configuration; needed only when the Indian Railways API/GTFS connector is configured.

As requested, these values are documented here only by variable name and role and are never printed.

## Blockers discovered during validation

1. P2 import path fails because `pytest` cannot import `app` as a package under the checked-in test command.
2. P5 import path fails because `pytest` is being run without the correct package/import context for `src`.
3. P4 route service and P5 route client are designed as external HTTP connectors; P5 integration depends on `P4_BASE_URL` and also requires a live route service to respond.
4. P3’s optional Copernicus satellite workflow depends on non-repository credentials in `.env`. They are documented here but no secret value is exposed.
5. P6’s CLIP verification branch depends on a Hugging Face token or local `transformers`/`torch` package availability.

## Components ready for integration

Only the API/service health and route capabilities discovered by test evidence, without any external API key loading, are currently ready in a weak sense:

- P3 is ready for an isolated service test path and uses a working test suite.
- P4 is ready for an isolated route service test path and uses a passing test suite.
- P6 is ready for a snapshot and local route simulation service path.

P1 and P2 remain blocked by import-root/package vocabulary and missing inference environment shape. P5 remains blocked by an import-root issue in its own test environment.
