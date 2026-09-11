# Component Audit: P1–P6

This repository audit is based on the checked-in code, README guidance, example environment files, and test folders only. No external API call, no dataset download, and no training run were performed while writing this audit.

## High-level component matrix

| Component | Purpose | Input | Output | Model | APIs | Tests | Status |
|---|---|---|---|---|---|---|---|
| P1 Flood | Estimate flood risk and flood probability per segment/district using rainfall, elevation, and river proximity. | Rainfall, terrain, river and optional historical flood training features. | JSON hazard score object with `flood_probability`, `contributing_factors`, and `scoring_method`. | Optional calibrated gradient boosted joblib artifact (`p1_flood_model.joblib`) with heuristic fallback. | Open-Meteo, OSM Overpass, optional Bhuvan / WRIS sources. | `p1-flood/tests/test_flood_score.py` | PARTIALLY_WORKING |
| P2 Landslide | Live landslide risk endpoint based on weather, terrain, land-cover, historical landslide count and optional satellite observation metadata. | Latitude, longitude, JSON request fields. | Landslide probability, risk level, confidence, model version and metadata. | Fallback heuristic plus optional trained `MODEL_PATH` joblib artifact. | Open-Meteo, NASA COOLR, OpenStreetMap Overpass, Microsoft Planetary Computer STAC. | `p2-landslide/tests/test_api.py`, `test_live_data.py`, `test_model_status.py`, `test_scoring.py`, `test_training.py` | PARTIALLY_WORKING |
| P3 Road Risk | Hybrid road-risk and disruption assessment combining accident model A with optional upstream P1/P2 and deterministic evidence fusion. | Road/location/timestamp/context and optional upstream probabilities. | `risk_probability`, `disruption_probability`, `operational_disruption_score`, `accessibility_score`, categories and evidence. | Active accident/traffic model A plus deterministic hybrid scoring. Model B and satellite CV are research only. | OSM/PBF research, GDELT public API, Copernicus Data Space (satellite, optional), IMD/CWC/NWIC feeds if available locally. | `p3-road-risk/tests/test_api.py`, `test_hybrid.py`, `test_incident_dataset.py`, `test_ml_pipeline.py`, `test_satellite_pipeline.py`, `test_road_closure_pipeline.py`, `test_road_geometry.py`, `test_uttarakhand_pwd_schema_audit.py` | PARTIALLY_WORKING |
| P4 Routing | Route optimization across OSM, weather, flood, landslide, IMD warnings, route news, rail/ferry multimodal context. | Origin and destination strings, route request model. | Route result object, `route_id`, travel time, risk fields, route alternatives. | No stable trained ML; uses deterministic risk engine and route scoring. | OpenStreetMap / Overpass, OSRM, Open-Meteo, Open-Meteo Flood, IMD WIS2 CAP, NRSC/ISRO Bhuvan, GDELT, Google News RSS, Indian Railways GTFS/URL. | `p4-path-optimization/tests/test_live_intelligence.py`, `test_router.py` | PARTIALLY_WORKING |
| P5 Logistics | Logistics API for shipments, shortage scoring, warehouse optimization and demand estimation; fetches P4 route facts. | Shipment, shortage, warehouse, demand objects. | Shipment and logistics decision outputs. | Explainable shortage model baseline; optional later XGBoost model artifact. | Local internal service plus HTTP call to P4 route endpoint. | `p5-logistics/tests/test_api.py` | WORKING_WITH_CONFIG |
| P6 Control Tower | Incident management, alerts, image verification, simulation, what-if control tower via FastAPI and optional downstream P3/P4/P5 HTTP integrations. | Incident and sensor payloads, image URLs, optional route/shipment simulation data. | Incident records, alerts, verified images results, control-tower overview and snapshots. | None (CLIP locally or through Hugging Face inference; optional). | IMD CAP WIS2, Hugging Face Inference API, optional P3/P4/P5 HTTP. | `p6-control-tower/tests/test_alerts.py`, `test_incidents.py`, `test_simulation.py`, `test_verify.py` | WORKING_WITH_CONFIG |

---

## P1 — Flood Intelligence

1. Purpose: Predict a flood probability for a segment/district, optionally calibrated with a trained flood model and a fallback transparent heuristic.
2. Main source directory: `p1-flood/src/`
3. Entry point: `python src/fetch_rainfall.py`, `python src/fetch_terrain.py`, `python src/flood_score.py`; optional training `python src/train_model.py --table ...`
4. Input format: Live fetch scripts read lat/lon and generate JSON output; training pipeline expects a canonical daily table with `date`, `segment_id`, `flood_event` and optional feature columns.
5. Output format: `data/sample_output.json` style JSON with `flood_probability`, `contributing_factors`, `scoring_method` and per-segment outputs.
6. ML model(s): Optional calibrated gradient-boosted joblib in `p1-flood/models/` with heuristic fallback; `HistGradientBoostingClassifier` in training code.
7. Training datasets: `build_training_table.py`, `prepare_indofloods.py` produce/prepare INDOFLOODS/IPED style training data, with weak negatives and approximate river network features.
8. Inference datasets: `data/rainfall_raw.json`, `data/terrain_raw.json`, and `data/sample_output.json` caches exist in the repo structure.
9. External APIs: Open-Meteo rainfall/elevation, OSM Overpass river proximity; optional Bhuvan/WRIS dataset access and India-WRIS/CWC historical sources.
10. Required API keys: No hard-coded key required by the code; optional token needed for Bhuvan access, but the source code does not implement that token.
11. Environment variables: None hard-coded; `src/fetch_rainfall.py` and `fetch_terrain.py` use live public URLs and no auth token.
12. Important dependencies: `requests`, `pandas`, `scikit-learn`, `joblib`, `numpy`.
13. Existing tests: `p1-flood/tests/test_flood_score.py` covers probability bounds and monotonicity.
14. Whether the component currently runs: It can run as a data fetch + scoring prototype, but the historical flood frequency and strong supervised labels are not yet comprehensive.
15. Known limitations: Historical non-event labels are weak; no complete flood frequency lookup; weak labels and missing calibrated model artifact still mean dry-run heuristics dominate when no model artifact is present.

## P2 — Landslide Intelligence

1. Purpose: Return disaster-aware live landslide probability from public environmental sources and a transparent fallback model.
2. Main source directory: `p2-landslide/app/` and top-level `build_gsi_susceptibility_dataset.py`, `train_model.py`.
3. Entry point: `uvicorn app.main:app --reload --port 8000` from `p2-landslide/`; `GET /api/v1/live-features` and `POST /api/v1/predictions/landslide`.
4. Input format: Request object includes `latitude`, `longitude`, optional `location_id` and route fields; the P2 code also accepts `latitude`/`longitude` query parameters.
5. Output format: JSON prediction object with `landslide_probability`, `risk_level`, `confidence`, `model_version`, plus `features` and `source_status` from the live endpoint.
6. ML model(s): Optional `MODEL_PATH` joblib artifact loaded in `app/scoring.py`; fallback heuristic model version `landslide_heuristic_v0` and env default `landslide_logistic_regression_v1`.
7. Training datasets: `data/demo_landslide_observations.csv`, `data/gsi_india_susceptibility.csv`, `data/verified_landslide_observations.template.csv`, and generated training data from `build_gsi_susceptibility_dataset.py`.
8. Inference datasets: Live Open-Meteo weather, elevation, NASA COOLR fallback historical count, OSM land cover / land use inference, and optional Planetary Computer STAC metadata.
9. External APIs: Open-Meteo Forecast and Elevation APIs, NASA COOLR ArcGIS, OSM Overpass, Microsoft Planetary Computer Sentinel-2 STAC.
10. Required API keys: None in the codebase; public or demo endpoints are used; external STAC access is best effort and typically keyless.
11. Environment variables: `MODEL_VERSION`, `MODEL_PATH`, `NASA_COOLR_URL`.
12. Important dependencies: `fastapi`, `uvicorn`, `httpx`, `requests`, `joblib`, `pydantic`, `numpy`, `pandas`, `sklearn` (training). 
13. Existing tests: `test_api.py`, `test_live_data.py`, `test_model_status.py`, `test_scoring.py`, `test_training.py`.
14. Whether the component currently runs: The service can start and run; at runtime it defaults to a heuristic if no model artifact is present.
15. Known limitations: The default risk engine is explicitly a transparent heuristic and not validated scientifically; satellite image discovery is optional and cannot block the service; training data is local, small, and labelled only partially.

## P3 — Road Risk

1. Purpose: Deterministic evidence-fusion road disruption risk engine that combines accident risk and optional P1/P2 hazard information.
2. Main source directory: `p3-road-risk/src/`
3. Entry point: `src/main.py` and `uvicorn src.main:app --reload`; route `POST /predict` and `POST /analyze` exposed through the FastAPI API.
4. Input format: `RoadRiskRequest`, `P3PredictionRequest`, road/location/time features plus optional hazard_context field; route-level upstream probabilities accepted opportunistically.
5. Output format: Pydantic JSON schema with `risk_probability`, `disruption_probability`, `operational_disruption_score`, `accessibility_score`, explanation and decomposed factors.
6. ML model(s): Active model A accident-risk model `current_model.json` and joblib artifact version; the hybrid engine is a deterministic, non-ml rule engine; model B (historical closure labels) and satellite CV are research-only.
7. Training datasets: Public Indian road accident archive, IoT traffic archive, PWD Uttaakhand schema sample, local road closure evidence/parquet and raw historical PWD routes; training-only local dataset artifacts inside `data/raw/training`.
8. Inference datasets: `data/raw/rainfall/IMD_rainfall_*.nc`, `data/raw/water_levels/cwc_river_levels.csv.csv`, `data/processed/road_closure/road_closure_events.parquet`, optional P1/P2 probabilities and OSM/PWD identity context.
9. External APIs: GDELT public API, Copernicus Data Space catalog and process APIs, OSM road map / PBF local context, IMD/CWC/NWIC public or local feeds, optional P1/P2 upstream services.
10. Required API keys: No required key for public sources; `CDSE_CLIENT_ID` / `CDSE_CLIENT_SECRET` only for the optional Sentinel satellite research pipeline.
11. Environment variables: `CDSE_CLIENT_ID`, `CDSE_CLIENT_SECRET`; environment file `.env` in `p3-road-risk/`.
12. Important dependencies: `fastapi`, `uvicorn`, `pydantic`, `requests`, `scikit-learn`, `joblib`, `osmium` and many local data processing dependencies.
13. Existing tests: `p3-road-risk/tests/test_all` include API tests, hybrid tests, satellite pipeline tests, road geometry tests, incident dataset tests and model tests.
14. Whether the component currently runs: It has a working API structure and internal deterministic engine; however, the full road disruption model B and satellite data flow remain incomplete or optional.
15. Known limitations: Model B is not trained from sufficient official labels; satellite/CV is not active in the score; OSM identity mapping is conservative and limited; no route-level closure claim is certified.

## P4 — Path Optimization

1. Purpose: Optimize routes across Northeast India with real OSM road graphs and risk-aware cost modeling, including weather, flood, landslide, IMD, and disaster news features.
2. Main source directory: `p4-path-optimization/src/`
3. Entry point: `uvicorn src.main:app --reload --port 8001` or `python src/main.py` if available; route `POST /api/v1/routes/optimize` and debug `GET /api/v1/data-sources`. 
4. Input format: JSON route request object with `origin`, `destination`, `cargo_type`, `priority`, plus `transport_mode`, `route_options` fields when provided.
5. Output format: `RouteResponse` JSON including `route_id`, `estimated_travel_time_minutes`, `distance_km`, `route_risk`, `weather_risk`, `flood_risk`, `landslide_risk`, `imd_warning_risk`, `news_risk`, and `safety_score`.
6. ML model(s): No trained ML model in the route engine. The route engine uses a deterministic risk scoring stack and data enrichment rather than a supervised classifier.
7. Training datasets: None; graph and risk scoring operate on live external resources and local caches.
8. Inference datasets: Overpass/OSM graph, OSRM routes, Open-Meteo and Flood APIs, IMD CAP, NRSC Bhuvan, GDELT and Google News RSS, optional Indian Railways timetables.
9. External APIs: OpenStreetMap Overpass, OSRM, Open-Meteo, Open-Meteo Flood, IMD WIS2 CAP, NRSC Bhuvan WMS, GDELT GKG GeoJSON and GDELT DOC, Google News RSS, Indian Railways GTFS or API.
10. Required API keys: No required key by default. Optional external configured service key: `INDIAN_RAIL_API_KEY` (used only if an Indian Railways service feed is configured).
11. Environment variables: `ROUTE_CORRIDOR_BUFFER_KM`, `ROUTE_MAX_DOWNLOAD_AREA_KM2`, `MAX_SNAP_DISTANCE_KM`, `OSM_TILE_LENGTH_KM`, `OSM_TILE_BUFFER_KM`, `OVERPASS_TIMEOUT_SECONDS`, `OVERPASS_ENDPOINTS`, `OSRM_ROUTING_URL`, `OSRM_TIMEOUT_SECONDS`, `OSRM_ALTERNATIVES`, `INDIAN_RAILWAYS_GTFS_PATH`, `INDIAN_RAILWAYS_GTFS_URL`, `INDIAN_RAIL_API_KEY`, `INDIAN_RAIL_API_BASE`, `IMD_CAP_MESSAGES_URL`, `NRSC_BHUVAN_WMS_URL`, `NRSC_LANDSLIDE_LAYER`, `NRSC_LANDSLIDE_GEOJSON`, and `P4` route configuration values.
12. Important dependencies: `fastapi`, `uvicorn`, `networkx`, `osmnx`, `geopy`, `httpx`, `shapely`, `pyproj`, `numpy`, `pandas`.
13. Existing tests: `tests/test_live_intelligence.py` and `tests/test_router.py` are present.
14. Whether the component currently runs: It has a FastAPI service and router engine, but some external live feeds are best effort, and graph generation / route quality depends on the OSM corridor and additional feed configuration.
15. Known limitations: P4 is data-latency and external-feed dependent; GDELT and Google News feeds are noisy and location-limited; rail passenger service is only modeled when GTFS or API feed is configured; no fake road edges or synthetic infrastructure should replace real mapping.

## P5 — Logistics

1. Purpose: Provide logistic/shipment management, shortage prediction baseline, demand, and warehouse optimization, and integrate with P4 route optimization to produce route facts from the P4 API.
2. Main source directory: `p5-logistics/src/`
3. Entry point: `uvicorn src.main:app --reload --port 8000` in `p5-logistics/`; FastAPI endpoints cover shipments, shortage, demand, warehouses and route integration.
4. Input format: Pydantic request objects such as `ShipmentInput`, `ShortageInput`, `DemandInput` and route optimization payloads.
5. Output format: JSON output objects such as `ShipmentOutput`, `ShortageOutput`, `DemandOutput`, route fields including `route_risk`, `estimated_travel_time_minutes`, and `route_id`.
6. ML model(s): Explainable shortage baseline model; a future XGBoost artifact is mentioned, but no trained artifact is active in the repo.
7. Training datasets: Warehouse, inventory and demand benchmark data in `p5-logistics/data/` and tests directly define inputs; no separate model training dataset is committed.
8. Inference datasets: Wares/inventory in memory or data files, and P4 route optimization responses via `P4_BASE_URL`.
9. External APIs: P4 route optimization service HTTP API via `P4_BASE_URL` and `httpx`; no direct third-party key-based API discovered.
10. Required API keys: No key is found. `P4_BASE_URL` is an environment variable for integration and is already documented in `.env.example`.
11. Environment variables: `P4_BASE_URL`, `P4_TIMEOUT_SECONDS` are used in `p5-logistics/src/p4_client.py` and `src/logistics.py`.
12. Important dependencies: `fastapi`, `uvicorn`, `httpx`, `pydantic`.
13. Existing tests: `p5-logistics/tests/test_api.py` covers health, shipment, shortage, and demand endpoints.
14. Whether the component currently runs: It can run as an internal logistics service; the P4 route client is configurable and defaults to `http://127.0.0.1:8001`.
15. Known limitations: P5 depends on P4 for route optimization facts; no stable external route API key is required, but P4 must be reachable. The shortage prediction is a baseline explainable model, not a trained ML model.

## P6 — Control Tower

1. Purpose: Independent incident, verification, alert, image classification, and what-if simulation service for operational logistics control.
2. Main source directory: `p6-control-tower/src/`
3. Entry point: `uvicorn src.main:app --host 127.0.0.1 --port 8006` from `p6-control-tower/`; route endpoints include `/api/v1/incidents`, `/api/v1/alerts/evaluate`, `/api/v1/simulation/what-if`, `/api/v1/control-tower/overview`.
4. Input format: Incident and verification payloads (`incident_id`, event fields, image URLs and exif metadata), alert evaluation payloads, simulation data from P4/P5 snapshots or upstream HTTP.
5. Output format: JSON incidents, alert lists, simulation results and an overview/power map state; image verification returns labels and confidence from CLIP.
6. ML model(s): CLIP model is optional, local fallback via `transformers` and remote Hugging Face Inference API via `HF_TOKEN`. No trained artifact is required.
7. Training datasets: Snapshot data in `data/snapshots/` and `data/` route shape records; no training dataset generation is active.
8. Inference datasets: Snapshots for P4/P5 route and shipment data; external IMD CAP alerts; optional P3/P4/P5 upstream responses when configured.
9. External APIs: IMD CAP WIS2 messages API; Hugging Face Inference API when `HF_TOKEN` configured; optional P3/P4/P5 base URLs.
10. Required API keys: Hugging Face token `HF_TOKEN` or `HUGGINGFACEHUB_API_TOKEN` is optional. No P3/P4/P5 keys are required. `P4_BASE_URL`, `P5_BASE_URL`, `P3_BASE_URL` are service configuration URLs rather than keys.
11. Environment variables: `DATABASE_URL` or `P6_DATABASE_URL`, `HF_TOKEN`, `HUGGINGFACEHUB_API_TOKEN`, `HF_CLIP_MODEL`, `P3_BASE_URL`, `P4_BASE_URL`, `P5_BASE_URL`, `IMD_CAP_MESSAGES_URL`, `P6_EXIF_MISMATCH_KM`.
12. Important dependencies: `fastapi`, `uvicorn`, `sqlalchemy`, `dotenv`, `transformers`, `torch`, `httpx`, `Pillow`; also `pytest`.
13. Existing tests: `test_alerts.py`, `test_incidents.py`, `test_simulation.py`, `test_verify.py`.
14. Whether the component currently runs: It has a defined FastAPI and tests; it can run locally using snapshots and an optional HF API token; if not configured, it must fall back to local CLIP or produce a degraded mode.
15. Known limitations: Upstream P3/P4/P5 remain optional; local image verification depends on CLIP availability or token; P6 does not import P1–P5 Python packages, so integration needs HTTP service connectors.

---

## Integration Risk Summary

This repository does not presently contain a single, monolith-ready migration. The strongest implementation hooks are P3/P4/P5/P6 as service APIs, while P1/P2 are local web service-style prediction components that fetch public data directly. The helpful signal is that most components are already separated by API and environment rather than internal package imports, but the external API/config architecture has a broad surface and many optional sources.
