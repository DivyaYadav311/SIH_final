# Pravah — AI-Powered Smart Logistics & Multi-Hazard Accessibility Platform

> **Smart India Hackathon (SIH) | Problem Statement: SIH26002**  
> *“Safer Journeys. Stronger North East.”*

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13-blue?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Leaflet](https://img.shields.io/badge/Leaflet-1.9.4-199900?logo=leaflet&logoColor=white)](https://leafletjs.com)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-100%25%20Passing-brightgreen)]()

---

## 📌 Executive Summary

The North Eastern Region (NER) of India—comprising Assam, Arunachal Pradesh, Meghalaya, Manipur, Mizoram, Nagaland, Tripura, and Sikkim—is critically vulnerable to natural disasters. Torrential monsoon cloudbursts, severe flash floods in the Brahmaputra and Barak basins, and widespread landslides along steep Himalayan slopes regularly sever arterial transit highways (such as NH-13, NH-27, and NH-6). When these single-corridor arteries fail, essential supplies—including emergency medicine, food grains, and petroleum—are blocked, isolating remote communities for days or weeks.

**Pravah** is an integrated, end-to-end AI-powered accessibility intelligence platform and disaster-resilient logistics control tower. It fuses real-time satellite earth observation data, meteorological radar telemetry, predictive machine learning models, multi-modal routing algorithms, and computer vision to deliver:
1. **Proactive Hazard Avoidance**: Predicting hazards before convoys depart rather than reacting after roads are blocked.
2. **Adaptive Multi-Modal Routing**: Finding optimal road and railway paths avoiding high-risk terrain.
3. **Automated Supply Chain Resilience**: Preventing commodity stockouts in vulnerable district warehouses.
4. **AI-Verified Incident Response**: Eliminating rumors and false alerts through satellite EXIF cross-referencing and Vision AI classification.

---

## 🏗️ System Architecture & Data Flow

Pravah unites six core microservices (P1 to P6) through a single unified high-throughput ASGI FastAPI server on port `8002`:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        PRAVAH WEB INTERFACE (HTML5 / CSS3 / ES6)                       │
│  Path Optimization • Risk Intelligence • Logistics Hub • Control Tower • What-If Sim   │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │ HTTP / JSON REST APIs
┌───────────────────────────────────────────▼────────────────────────────────────────────┐
│                       PRAVAH UNIFIED FASTAPI ENGINE (Port 8002)                        │
├───────────────────────┬───────────────────────┬────────────────────────────────────────┤
│  P1: Flood Model      │  P2: Landslide Model  │  P3: Road Disruption Risk Model        │
│  (Sentinel-1 SAR)     │  (DEM + GPM Rain)     │  (CDSE Satellite Multispectral)        │
├───────────────────────┼───────────────────────┼────────────────────────────────────────┤
│  P4: Adaptive Router  │  P5: Logistics Engine │  P6: Incident & Verification Tower     │
│  (OSRM + Rail GTFS)   │  (Runway & Shortage)  │  (CLIP Vision AI + What-If Simulation) │
├───────────────────────┴───────────────────────┴────────────────────────────────────────┤
│  External Intelligence: Open-Meteo • IMD WIS2 CAP • Copernicus CDSE • Google Gemini AI │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔍 Detailed Section-by-Section Breakdown

### 1. Real-Time Multi-Hazard Path Optimization (P4 Routing Engine)
* **What It Does**:
  Calculates primary and alternative transit corridors connecting Northeast commercial hubs, border outposts, and district centers. When environmental models detect high risk along a highway segment, Pravah penalizes that segment's traversal weight and reroutes vehicles through safer bypasses or intermodal rail transfers.
* **Input Parameters**:
  - `Origin` & `Destination` (e.g., Guwahati ➔ Tawang, Siliguri ➔ Shillong).
  - `Cargo Type` (Pharmaceuticals & Vaccines, Perishable Food, Petroleum & LPG, Heavy Machinery, General Freight).
  - `Priority` (Critical Emergency, High Commercial, Standard).
  - `Transport Mode` (Road Only, Multimodal Rail + Road, All-Terrain Military Convoy).
  - `Optimization Goal` (Safest Corridor, Fastest Transit, Maximum Fuel Economy).
* **Outputs Generated**:
  - Route distance (km), estimated transit duration (hours & minutes), multi-hazard risk index (0–100%).
  - Detailed segment-by-segment waypoints, elevation profile, and map geometry.
  - Recommended detours with additional travel time and bypass distance calculations.
* **Data Sources & APIs**:
  - **OpenStreetMap (OSRM)**: Highway topologies, road surface types, speed limits, and bridge locations.
  - **Indian Railways GTFS**: Freight parcel express routes and terminal transshipment nodes.
  - **Endpoints**: `POST /api/v1/routes/optimize`, `GET /api/v1/geocode`, `GET /api/v1/reverse-geocode`.

---

### 2. Multi-Hazard Predictive Intelligence (P1, P2, P3 Pipeline)
Before any route is optimized, Pravah automatically executes a chained multi-hazard inference pipeline:

```
[User Corridor Request]
         │
         ▼
┌──────────────────┐     Rainfall Telemetry
│ P1: Flood Risk   │ ─────────────────────────► Discharge & Inundation Probability
└────────┬─────────┘
         │ Soil Saturation & Slope
         ▼
┌──────────────────┐     Geotechnical Hazard
│ P2: Landslide    │ ─────────────────────────► Slope Instability Probability
└────────┬─────────┘
         │ Surface Roughness & Optical Indices
         ▼
┌──────────────────┐     Corridor Disruption Index
│ P3: Road Risk    │ ─────────────────────────► Composite Segment Penalty Score
└──────────────────┘
```

#### P1: Flood Intelligence
* **What It Does**: Estimates inundation probability along river plains and low-lying highway corridors, tracking river discharge at critical hydrological stations.
* **Data Sources**: Copernicus Sentinel-1 SAR (Synthetic Aperture Radar) for water surface backscatter mapping, Open-Meteo Global Flood API, and Central Water Commission (CWC) river gauges.
* **Model**: Random Forest & XGBoost classifiers trained on historical Assam flood extents.
* **Endpoint**: `POST /api/v1/predictions/flood`.

#### P2: Landslide Intelligence
* **What It Does**: Assesses slope failure susceptibility triggered by cumulative monsoon precipitation in high-altitude ghat roads (e.g., NH-13 Trans-Arunachal Highway).
* **Data Sources**: ALOS/SRTM Digital Elevation Models (DEM) for slope angles, ISRO/NRSC Bhuvan Landslide Hazard Zonation maps, and 72-hour precipitation accumulation.
* **Model**: Geotechnical slope stability gradient boosted regressor.
* **Endpoint**: `POST /api/v1/predictions/landslide`.

#### P3: Road Risk & Accessibility Scoring
* **What It Does**: Evaluates physical road passability, combining structural road vulnerability, satellite vegetation/water index anomalies, and terrain ruggedness into a single disruption index (0.0 to 1.0).
* **Data Sources**: Copernicus Data Space Ecosystem (CDSE) Sentinel-2 optical imagery (NDVI/NDWI index changes) and OpenStreetMap road classifications.
* **Endpoint**: `POST /api/v1/road-risk/predict`.

---

### 3. Hyperlocal Weather Telemetry & 24-Hour Diurnal Curve
* **What It Does**:
  Provides transport managers with live, sensor-accurate atmospheric data along the selected route corridor.
* **Live Environmental Metrics**:
  - **Ambient Temperature**: Real-time reading (°C).
  - **Precipitation / Rainfall**: Live precipitation rate (mm) and 24h accumulation.
  - **Relative Humidity**: Sensor humidity percentage (%).
  - **Wind Speed & Direction**: Real-time velocity (km/h) for high-profile truck rollover risk.
  - **Air Quality Index (AQI)**: Particulate matter (PM2.5 / PM10) monitoring for visibility hazards.
* **24-Hour Diurnal Forecast Curve**:
  - An interactive SVG temperature graph displaying hour-by-hour diurnal temperature swings (`Low` to `Peak`).
  - Precipitation probability timeline slots (`💧 % POP`) indicating safe departure windows.
* **Data Sources & APIs**:
  - Open-Meteo Weather Forecast API (`https://api.open-meteo.com/v1/forecast`).
  - Open-Meteo Air Quality API (`https://air-quality-api.open-meteo.com/v1/air-quality`).

---

### 4. Real-Time Disaster News & Situational Feed
* **What It Does**:
  Continuously scrapes, deduplicates, and presents geotargeted highway hazard news, road collapse bulletins, and flash flood alerts.
* **Key Features**:
  - **Strict Freshness Window**: Evaluates news timestamps to only show live news or reports published within the last 7 days, automatically discarding obsolete articles.
  - **Direct Source Verification**: Every card contains direct outbound links to the original publisher or Google News query.
  - **Deep Situation Reports**: Clicking any report opens an in-page situation modal displaying disruption impact ratings, reported coordinates, and telemetry analysis.
* **Data Sources & APIs**:
  - GDELT Project live regional disaster feeds.
  - Google News RSS engine with geographic NER corridor filters.
  - Official IMD WIS2 CAP Emergency Warning Feed (`https://wis2box.imd.gov.in/oapi/collections/messages/items`).

---

### 5. Generative AI Strategic Logistics Advisory (Google Gemini)
* **What It Does**:
  Synthesizes complex numerical predictions (flood probability, landslide slope hazard, weather radar, and active alerts) into clear, actionable tactical advice for transport command officers and drivers.
* **Advisory Outputs**:
  - **Strategic Assessment**: Clear executive summary of corridor passability.
  - **Convoy Operations**: Recommended speed caps, convoy spacing, and night driving curfews.
  - **Safety Protocols**: Required emergency equipment (winches, satellite radios, medical oxygen).
  - **Safe Staging Zones**: Specific safe parking waypoints before entering red-zone ghat sections.
* **Models & Fallback**:
  - Primary: `gemini-3.7-flash` (temperature 0.2, timeout 15s).
  - Automatic Fallback: Resilient multi-tier fallback to `gemini-3.6-flash` and structured rule-based advisories if quota is exhausted.
* **Endpoint**: `POST /api/v1/ai/advisory`.

---

### 6. P5 Logistics & Supply Chain Shortage Predictor
* **What It Does**:
  Monitors warehouse inventory levels across Northeast regional storage hubs (Guwahati, Tezpur, Silchar, Dibrugarh, Shillong, Tawang) and models supply chain resilience during natural disruptions.
* **Key Metrics**:
  - **Buffer Runway (Days)**: Time until local supplies are completely exhausted based on current district population burn rates.
  - **Stockout Probability**: Predictive probability of supply failure across Critical Medicines, Food Grains, Fuel/Diesel, and Water Purification tablets.
  - **Automated Dispatch Scheduling**: Re-allocates relief convoys from surplus warehouses to at-risk forward depots.
* **Endpoints**:
  - `GET /api/v1/shipments`: Lists all active relief shipments, cargo manifests, and revised ETAs.
  - `POST /api/v1/shipments`: Creates and schedules a new freight convoy.
  - `GET /api/v1/warehouses`: Warehouse capacity, coordinates, and current stock status.
  - `GET /api/v1/inventory`: Granular SKU stock breakdown per facility.
  - `POST /api/v1/predictions/shortage`: ML shortage risk calculation.

---

### 7. P6 Control Tower & Field Incident Verification
* **What It Does**:
  The central operational command dashboard for field incident intake, visual verification, and regional alert monitoring.
* **Field Incident Submission**:
  - Field drivers or local disaster officers submit geotagged reports with GPS coordinates, affected highway ID, hazard type, and attached photos.
  - Supports browser file upload (`data:image/...;base64,...`) and external image URLs.
* **Vision AI Image Verification (CLIP)**:
  - Uses OpenAI CLIP (`openai/clip-vit-base-patch32`) hosted on Hugging Face / local inference to classify incident photos against zero-shot candidate labels (`LANDSLIDE`, `FLOOD`, `ROAD_BLOCKED`, `ACCIDENT`, `CLEAR`).
  - Extracts EXIF metadata from photos and calculates Haversine distance between reported GPS and photo capture coordinates to detect and reject fraudulent submissions.
* **Alert Severity Scoring Engine**:
  - Dynamic evaluator that calculates composite severity from flood and landslide probabilities, classifying threats into `CRITICAL`, `HIGH`, or `MEDIUM` with corresponding command protocols.
* **Endpoints**:
  - `GET /api/v1/control-tower/overview`: Aggregates active incidents, open warnings, and shipments at risk.
  - `GET /api/v1/incidents`: Retrieves incident logs with confidence ratings.
  - `POST /api/v1/incidents`: Registers a new incident report.
  - `POST /api/v1/incidents/{id}/verify`: Triggers AI vision verification and EXIF validation.

---

### 8. What-If Scenario Disruption Simulator (P6 Engine)
* **What It Does**:
  Allows disaster management authorities to stress-test regional logistics networks by simulating hypothetical extreme disruption scenarios before they occur.
* **Supported Scenarios**:
  - `Major Mountain Landslide Severance` (e.g. NH-13 cutoff).
  - `River Basin Flood Inundation` (e.g. NH-27 Lumding corridor submerged).
  - `Critical Bridge Failure / Washout`.
* **Cascade Impact Analytics**:
  - Number of disrupted road segments and affected freight convoys.
  - Additional average travel delay (hours and minutes).
  - Increased shortage risk percentage for downstream recipient districts.
  - Alternative route bypass generation with complete Leaflet map geometry.
* **Endpoint**: `POST /api/v1/simulation/what-if`.

---

## 💻 Complete Technology Stack

| Domain | Technology / Library | Purpose in Pravah |
|---|---|---|
| **Backend Web Server** | **FastAPI** & **Uvicorn** | High-performance asynchronous REST API backend (Port 8002). |
| **Database & ORM** | **SQLAlchemy** & **SQLite** | Persistent storage for incidents, alerts, shipments, and simulation logs. |
| **Validation & Schemas** | **Pydantic v2** | Strict API request/response validation contracts across all microservices. |
| **Vision AI** | **Hugging Face Transformers** / **CLIP** | Zero-shot image classification for road incident verification (`clip-vit-base-patch32`). |
| **Generative AI** | **Google Gemini 3.7 / 3.6 Flash** | Real-time tactical emergency logistics advisories and situation reports. |
| **Machine Learning** | **Scikit-Learn** & **XGBoost** | Flood discharge modeling, landslide slope stability, and road vulnerability scoring. |
| **Image & EXIF Processing** | **Pillow (PIL)** | Image parsing, format conversion, and EXIF GPS metadata extraction. |
| **Mapping & GIS** | **Leaflet.js 1.9.4** | Interactive map layers (CartoDB, OpenStreetMap, Satellite, Risk Overlays). |
| **Routing Engine** | **OSRM (OpenStreetMap)** & **NetworkX** | Road network graph generation, Dijkstra/A* pathfinding, and detour calculations. |
| **Meteorological Data** | **Open-Meteo APIs** | Real-time weather telemetry, precipitation rates, humidity, and air quality. |
| **Government Alerts** | **IMD WIS2 CAP Feed** | Official India Meteorological Department Common Alerting Protocol emergency bulletins. |
| **Frontend UI** | **Vanilla HTML5 & CSS3** | Custom dark/light glassmorphic UI design system with zero build dependencies. |

---

## 🚀 Installation & Local Deployment

### 1. Prerequisites
- **Python**: Version `3.11`, `3.12`, or `3.13`.
- **Git**: Installed and configured.
- **Modern Web Browser**: Google Chrome, Microsoft Edge, Mozilla Firefox, or Safari.

### 2. Clone Repository
```bash
git clone https://github.com/DivyaYadav311/SIH_final.git
cd SIH_final/NER-Smart-Logistics
```

### 3. Configure Environment Variables (`.env`)
Ensure `.env` exists in `NER-Smart-Logistics/.env`:
```ini
# Copernicus Data Space Ecosystem (CDSE)
CDSE_CLIENT_ID=your_cdse_client_id
CDSE_CLIENT_SECRET=your_cdse_secret

# Google Gemini AI Intelligence
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-3.7-flash
GEMINI_TIMEOUT_SECONDS=15
GEMINI_TEMPERATURE=0.2

# Hugging Face CLIP Vision AI
HF_TOKEN=your_hf_token
HF_CLIP_MODEL=openai/clip-vit-base-patch32

# Inter-Service Communication (Unified Server Default)
P3_BASE_URL=http://127.0.0.1:8002
P4_BASE_URL=http://127.0.0.1:8002
P5_BASE_URL=http://127.0.0.1:8002
```

### 4. Install Dependencies
```bash
python -m pip install -r requirements.txt
```

### 5. Launch the Server
You can launch using the provided batch launcher:
```bash
# Double click start.bat or run from terminal:
start.bat
```
Or directly using Uvicorn:
```bash
python -m uvicorn server.unified_server:app --host 127.0.0.1 --port 8002
```

Open your browser and navigate to:
```
http://127.0.0.1:8002/
```

---

## 📑 Complete API Specification

All routes are served on `http://127.0.0.1:8002`:

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | System health check reporting status of all P1–P6 modules. |
| `POST` | `/api/v1/routes/optimize` | Computes multimodal route with risk penalties and alternative paths. |
| `GET` | `/api/v1/geocode` | Geocodes a place name into latitude/longitude coordinates. |
| `GET` | `/api/v1/reverse-geocode` | Converts latitude/longitude coordinates into a human-readable address. |
| `POST` | `/api/v1/predictions/flood` | Returns flood inundation probability and discharge warnings. |
| `POST` | `/api/v1/predictions/landslide` | Returns slope failure susceptibility and saturation score. |
| `POST` | `/api/v1/road-risk/predict` | Evaluates road physical accessibility and disruption score. |
| `POST` | `/api/v1/ai/advisory` | Generates strategic Gemini AI situation reports and driver advice. |
| `GET` | `/api/v1/shipments` | Retrieves all active freight convoys and revised delivery ETAs. |
| `POST` | `/api/v1/shipments` | Dispatches and registers a new relief shipment. |
| `GET` | `/api/v1/warehouses` | Lists regional warehouse locations and stock capacities. |
| `GET` | `/api/v1/inventory` | Returns granular commodity stock levels across all hubs. |
| `POST` | `/api/v1/predictions/shortage` | Forecasts commodity stockout risk and buffer runway. |
| `GET` | `/api/v1/control-tower/overview` | Aggregated command KPIs (open incidents, active alerts, at-risk loads). |
| `GET` | `/api/v1/control-tower/map-state` | Active spatial layer of verified incidents and risk hot-spots. |
| `GET` | `/api/v1/incidents` | Lists field incidents with filter support (landslide, flood, verified). |
| `POST` | `/api/v1/incidents` | Reports a new hazard with optional photo evidence. |
| `POST` | `/api/v1/incidents/{id}/verify` | Executes zero-shot CLIP vision verification and EXIF GPS check. |
| `POST` | `/api/v1/simulation/what-if` | Runs multi-hazard cascade disruption simulation. |

---

## 🧪 Testing & Verification

Run the test suites across all modules:
```bash
# Run P6 Control Tower, verification, and simulation tests
python -m pytest NER-Smart-Logistics/p6-control-tower/tests

# Run P5 Logistics, inventory, and supply shortage tests
python -m pytest NER-Smart-Logistics/p5-logistics/tests

# Run P3 Road risk and satellite pipeline tests
python -m pytest NER-Smart-Logistics/p3-road-risk/tests
```

---

## 👥 Contributors

Developed with dedication for the **Smart India Hackathon**:

- **Manvi Sinha** ([@manvisinhan4500](mailto:manvisinhan4500@gmail.com))
- **Divya Yadav** ([@DivyaYadav311](https://github.com/DivyaYadav311))
- **Arni Goyal** ([@ArniGoyal](https://github.com/ArniGoyal))
- **Khwaish** ([@Khwaish06](https://github.com/Khwaish06))
- **Lavanya**
- **Mahi**

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
