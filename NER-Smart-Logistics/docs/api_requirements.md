# API and Key Requirements Inventory

This document lists every external API or key requirement discovered in the checked-in P1–P6 component structure. It does not print any API key value. It does document environment variables and expected config locations.

| Service | Component | Purpose | Required/Optional | Environment variable | Where the key or configuration should be added | Can the component run without it? |
|---|---|---|---|---|---|---|
| Open-Meteo Forecast and Elevation | P1 Flood | Rainfall and elevation input fetch | Optional public service | None | No key. Use public endpoint. | Yes |
| OpenStreetMap Overpass | P1 Flood | Nearest river / waterway geometry feature | Optional public service | None | No key. Use public endpoint. | Yes |
| Bhuvan / NRSC | P1 Flood, P4 Routing | Optional official terrain or landslide hazard context | Optional | `NRSC_BHUVAN_WMS_URL` (P4), optional Bhuvan token not coded | In `p4-path-optimization/.env` or project .env; for P1, Bhuvan token would be manually requested by the service owner and added into the environment used by the service. | Yes, public fallback continues |
| Open-Meteo Forecast and Elevation | P2 Landslide | Live weather, precipitation and elevation | Required for the service to fetch live input features | None | No key. Use public endpoint. | No, if the service relies on live features; fallback sources still allow degraded mode |
| NASA COOLR ArcGIS | P2 Landslide | Historical landslide event count around the point | Optional public service | `NASA_COOLR_URL` | Add in P2 environment, default URL is in code; no key | Yes, the service falls back |
| OpenStreetMap Overpass | P2 Landslide | Land-cover/land-use mapping | Optional public service | None | No key. Add endpoint if needed. | Yes, fallback land-cover categories remain |
| Microsoft Planetary Computer STAC | P2 Landslide | Sentinel-2 image metadata discovery | Optional research/provenance | None | No key. Public STAC request structure used. | Yes |
| GDELT public API | P3 Road Risk | Historical road-impact evidence discovery | Optional research/public feed | `GDELT_API_URL` default | In `p3-road-risk/.env.example` and component `.env`; no key required | Yes |
| Copernicus Data Space Ecosystem (CDSE) | P3 Road Risk | Sentinel satellite imagery and processing experiments | Optional research, not required for production hybrid score | `CDSE_CLIENT_ID`, `CDSE_CLIENT_SECRET` | `p3-road-risk/.env` or environment used by the service; example file shows variable names in `.env.example` | Yes, product route can continue without satellite image processing |
| OpenStreetMap Overpass / OSRM | P4 Routing | Road graph and route geometry / OSRM fallback | Required for real mapped routing | `OVERPASS_ENDPOINTS`, `OSRM_ROUTING_URL`, `OSRM_TIMEOUT_SECONDS`, `OSRM_ALTERNATIVES` | Add in `p4-path-optimization/.env` or repo environment; these are config values not keys | No, P4 needs some mapped road graph or OSRM route provider |
| Open-Meteo Weather and Flood | P4 Routing | Weather and flood risk enrichment | Required when route enrichment is requested | `WEATHER_API_URL`, `FLOOD_API_URL` default public URLs; no key | Use public service; no key | Yes, the route can still run with risk model fallback |
| IMD WIS2 CAP public feed | P4 Routing and P6 Control Tower | Official warnings feed | Optional public service | `IMD_CAP_MESSAGES_URL` | Add/override in `p4-path-optimization/.env` or `p6-control-tower/.env`; default URL is already in code | Yes, alerts can be empty or a fallback route can still be produced |
| NRSC / ISRO Bhuvan | P4 Routing | Landslide hazard layer metadata / WMS layer access | Optional public context | `NRSC_BHUVAN_WMS_URL`, `NRSC_LANDSLIDE_LAYER`, `NRSC_LANDSLIDE_GEOJSON` | In `p4-path-optimization/.env` or runtime environment | Yes, P4 route engine can avoid the NRSC landslide layer |
| GDELT and Google News RSS | P4 Routing | Disaster news risk and location detection | Optional public service | None | No key. Public APIs and RSS feed. | Yes |
| Indian Railways feed | P4 Routing | Multimodal train-service availability | Optional | `INDIAN_RAILWAYS_GTFS_PATH`, `INDIAN_RAILWAYS_GTFS_URL`, `INDIAN_RAIL_API_KEY`, `INDIAN_RAIL_API_BASE` | Add in `p4-path-optimization/.env` or environment; no track geometry is treated as train service | Yes, rail context remains optional |
| P4 route service | P5 Logistics | Route optimization integration | Required for route-aware logistics operation | `P4_BASE_URL`, `P4_TIMEOUT_SECONDS` | Add configuration in `p5-logistics/.env` and optionally in repo-level `.env` | Yes, route integration is optional but shipment endpoints will fail route enrichment when unreachable |
| Hugging Face Inference API | P6 Control Tower | Optional CLIP classification via HF inference API (instead of local model) | Optional | `HF_TOKEN` or `HUGGINGFACEHUB_API_TOKEN`, `HF_CLIP_MODEL` | Add in `p6-control-tower/.env` or repo root `.env` | Yes, local CLIP may be used instead |
| P3 upstream service | P6 Control Tower | Optional road-risk evaluation inputs | Optional | `P3_BASE_URL` | Add in `p6-control-tower/.env` or repo root `.env` | Yes, control tower can run with snapshots fallback |
| P4 upstream service | P6 Control Tower | Optional route optimization inputs | Optional | `P4_BASE_URL` | Add in `p6-control-tower/.env` or repo root `.env` | Yes, snapshots can be used if not configured |
| P5 upstream service | P6 Control Tower | Optional shipment simulation inputs | Optional | `P5_BASE_URL` | Add in `p6-control-tower/.env` or repo root `.env` | Yes, snapshots can be used if not configured |
| Database URL | P6 Control Tower | Local SQLite or custom database | Optional service dependency | `DATABASE_URL` or `P6_DATABASE_URL` | Add in `p6-control-tower/.env` or repo `.env`; defaults to SQLite in `data/p6.db` | Yes, default local SQLite is auto-created |

## Notes on missing keys and public endpoints

- The repository currently contains a committed `.env` in `p3-road-risk/` with real-looking `CDSE_CLIENT_ID` and `CDSE_CLIENT_SECRET` values. This audit does not print those values and does not need them to continue. They are treated as a secret configuration audit item only.
- No external API key is required for the base P1/P2 Open-Meteo and OSM Overpass workflows.
- Public GDELT, Google News, IMD WIS2 and most OSM/OSRM services are documented as public or low-cost/no-key services.
- Optional service tokens are not required to run the component in a degraded or fallback mode; the code acts explicitly that way.
