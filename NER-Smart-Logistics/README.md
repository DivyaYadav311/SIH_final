<![CDATA[# 🚀 PRAVAH — AI-Powered Smart Logistics & Accessibility Intelligence Platform

> **Pravah — Safer Journeys. Stronger North East.**
> Smart India Hackathon (SIH 26002)

---

## 📋 Table of Contents

- [Overview](#overview)
- [The Problem](#the-problem)
- [Our Solution](#our-solution)
- [System Architecture](#system-architecture)
- [Module Deep Dive (P1–P6)](#module-deep-dive)
- [API & Data Source Inventory](#api--data-source-inventory)
- [AI & Machine Learning Pipeline](#ai--machine-learning-pipeline)
- [Technology Stack](#technology-stack)
- [User Roles & Access Model](#user-roles--access-model)
- [How It All Works Together](#how-it-all-works-together)
- [Business Model & Deployment](#business-model--deployment)
- [Future Roadmap](#future-roadmap)
- [Getting Started](#getting-started)
- [Project Structure](#project-structure)

---

## Overview

**Pravah** is a unified, AI-powered Smart Logistics and Accessibility Intelligence Platform built specifically for India's **North Eastern Region (NER)**. It addresses one of the country's most critical logistical nightmares — getting essential supplies like medicines, food, and construction materials into remote districts where landslides, floods, and infrastructure gaps routinely cut off connectivity for days or even weeks.

The platform integrates **six intelligent microservices** (P1–P6), a **Gemini AI advisory engine**, and a **professional government-grade web dashboard** into a single, deployable backend running on **FastAPI + Python**. Every prediction — flood, landslide, road disruption, optimal route — is powered by **real, live APIs** and **genuine ML models**, not mock data.

**Named "Pravah"** (meaning "flow" in Hindi), the platform ensures the uninterrupted flow of essential goods through the most hostile terrain in India.

---

## The Problem

The North Eastern Region faces **unique logistics challenges** that no other Indian region encounters at this scale:

| Challenge | Impact |
|---|---|
| **Extreme Terrain** | 70%+ mountainous; single-lane highways clinging to hillsides |
| **Monsoon Fury** | 2,000–11,000 mm annual rainfall; 4-6 months of continuous rain |
| **Landslides** | 500+ landslides/year blocking NH-44, NH-6, NH-13 and lifeline corridors |
| **Floods** | Brahmaputra basin floods affecting 40+ districts annually |
| **Limited Connectivity** | Many districts have only 1-2 access roads; one blockage = total isolation |
| **Supply Chain Fragility** | Medicine shortages within 48 hours of a road cut; food price spikes of 200-400% |
| **Manual Monitoring** | Government officials rely on phone calls and WhatsApp groups to track road status |

**The human cost**: When NH-44 (the lifeline connecting Manipur and Nagaland to the rest of India) gets blocked by a landslide near Noney, 4+ million people lose access to critical supplies. Response decisions are made blindly because no one has a unified real-time picture.

---

## Our Solution

Pravah replaces manual, phone-based logistics coordination with an **AI-powered unified intelligence platform** that:

1. **Predicts** disasters before they happen (floods, landslides, road disruptions)
2. **Monitors** road, bridge, and transport accessibility in real-time across all NER districts
3. **Optimizes** routes considering hazards, not just distance — finding the safest practical path
4. **Manages** supply chains with shortage prediction and warehouse optimization
5. **Coordinates** emergency response through a control tower with incident verification and what-if simulation
6. **Advises** dispatchers through Gemini AI-generated tactical intelligence for every corridor

### How It's Different

| Existing Approach | Pravah |
|---|---|
| Road status via phone calls to PWD | Real-time multi-hazard intelligence map |
| Route planning via Google Maps (no hazard awareness) | AI-optimized routing considering flood, landslide, weather, and news |
| Supply planning based on historical estimates | ML-powered demand and shortage prediction |
| Incident reporting via WhatsApp images | CLIP-verified, GPS-validated, EXIF-checked incident reports |
| Decision-making in isolation | Unified control tower with what-if simulation |

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     PRAVAH UNIFIED BACKEND                         │
│                    FastAPI · Port 8002                              │
│                                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │ P1 Flood │  │P2 Land-  │  │ P3 Road  │  │ P4 Route         │   │
│  │ Intel    │→ │slide     │→ │ Risk &   │→ │ Optimization     │   │
│  │          │  │ Intel    │  │Disruption│  │                  │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────────┘   │
│       ↓             ↓             ↓               ↓               │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    P6 Control Tower                          │  │
│  │   Incidents · Alerts · Simulation · WebSocket Live Feed     │  │
│  └──────────────────────────────────────────────────────────────┘  │
│       ↑                                                            │
│  ┌──────────┐  ┌──────────────────┐  ┌─────────────────────────┐  │
│  │P5 Supply │  │ Gemini AI        │  │ Frontend Dashboard      │  │
│  │Chain &   │  │ Advisory Engine  │  │ (HTML/CSS/JS + Leaflet) │  │
│  │Logistics │  │ (gemini-3.7)     │  │                         │  │
│  └──────────┘  └──────────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────────────────┐
│                      EXTERNAL DATA SOURCES                         │
│                                                                     │
│  Weather    │ Open-Meteo Forecast + Flood APIs (free, no key)      │
│  Terrain    │ Open-Meteo Elevation (Copernicus GLO-90 DEM)         │
│  Rivers     │ OpenStreetMap Overpass API (waterway proximity)      │
│  Landslides │ NASA COOLR · GSI Inventory · NRSC/ISRO Bhuvan       │
│  Satellite  │ Copernicus Data Space (Sentinel-2 scene metadata)    │
│  Roads      │ OpenStreetMap + OSRM routing engine                  │
│  Warnings   │ IMD WIS2 CAP stream (official weather alerts)        │
│  News       │ GDELT + Google News RSS (geo-located disaster news)  │
│  Rail       │ Indian Railways API/GTFS                              │
│  AI         │ Google Gemini 3.7 Flash (route advisory)             │
│  Vision     │ HuggingFace CLIP (incident image verification)       │
│  Satellite  │ Copernicus CDSE (Sentinel-2 optical imagery)         │
└─────────────────────────────────────────────────────────────────────┘
```

### Data Flow: A Real Scenario

When a government dispatcher wants to send medicine from Guwahati to Kohima:

1. **P1** checks flood probability along the corridor using live rainfall + elevation + river proximity
2. **P2** checks landslide susceptibility using live terrain slope + precipitation + historical inventory
3. **P3** fuses P1 + P2 outputs with active incidents, road vulnerability, and traffic data into a **disruption score**
4. **P4** builds candidate routes on real OSM road networks, scores them with weather + IMD warnings + disaster news, and selects the **safest practical route**
5. **P5** manages the shipment, predicts if the destination district will face a shortage, and optimizes warehouse allocation
6. **P6** receives driver incident reports (with AI-verified photos), runs what-if simulations ("what if NH-44 gets blocked?"), and pushes real-time alerts via WebSocket
7. **Gemini AI** generates a tactical advisory: "Route risk is HIGH due to active IMD cyclone warning; recommend convoy staging at Nagaon with satellite communication..."

---

## Module Deep Dive

### P1 — Flood Intelligence Engine

**Purpose**: Predict flood inundation probability per location/segment.

| Component | Detail |
|---|---|
| **Live Rainfall** | Open-Meteo API — current + 7/14/30-day cumulative precipitation |
| **Elevation** | Open-Meteo Elevation API (Copernicus GLO-90 DEM at 90m resolution) |
| **River Proximity** | OSM Overpass API — nearest mapped waterway distance |
| **ML Model** | HistGradientBoosting classifier trained on INDOFLOODS/IPED data with Platt calibration |
| **Fallback** | Transparent weighted heuristic: 60% rainfall + 25% river + 15% elevation |
| **Features** | `rainfall_1d/3d/7d/14d/30d_mm`, `rainfall_anomaly_7d/30d`, `elevation_m`, `river_proximity_km`, `lat`, `lon`, `month` |
| **Training** | Chronological 60/20/20 split; validation-period Platt calibration; metrics on future test period |
| **Endpoint** | `POST /api/v1/predictions/flood` (lat/lon required, all else auto-fetched) |

### P2 — Landslide Susceptibility Engine

**Purpose**: Predict landslide susceptibility for any coordinate, fetching all features live.

| Component | Detail |
|---|---|
| **Weather** | Open-Meteo Forecast — temperature, humidity, hourly/6h/24h/7d precipitation |
| **Terrain** | Open-Meteo Elevation API + Horn method slope/aspect from 3×3 DEM grid |
| **Historical** | NASA COOLR — historical landslide count within 25 km radius |
| **Land Cover** | OpenStreetMap Overpass — nearest land-use/natural feature classification |
| **Satellite** | Copernicus CDSE — Sentinel-2 scene metadata discovery (optional) |
| **ML Model** | GSI India inventory-trained susceptibility model (geographic grid holdout) |
| **Fallback** | Transparent weighted heuristic (explicitly labeled, not a calibrated probability) |
| **Endpoint** | `POST /api/v1/predictions/landslide` (lat/lon only required) |

### P3 — Road Risk & Disruption Intelligence

**Purpose**: Fuse all hazard evidence into a per-road **disruption probability** and **accessibility score**.

| Component | Detail |
|---|---|
| **Upstream Inputs** | P1 flood probability + P2 landslide probability (optional, graceful degradation) |
| **Accident Model** | HistGradientBoosting trained on 20,000 Indian road accident records (v002, 17 features) |
| **Hybrid Engine** | Deterministic weighted evidence fusion: flood 40% + landslide 40% + traffic 20% |
| **Environmental** | IMD rainfall, CWC/NWIC river telemetry, terrain slope, vulnerability factors |
| **Synergy** | Co-occurring flood+landslide bonus (capped at 10%) |
| **Spatial Decay** | `exp(-distance_km / 5km)` for incident proximity |
| **Temporal Decay** | `exp(-age_hours / 24h)` for incident recency |
| **Outputs** | `disruption_probability`, `accessibility_score` (0-100), `risk_level`, evidence completeness, explanation |
| **94 Tests** | Full coverage of formulas, bounds, decay, category boundaries, API compatibility |
| **Endpoint** | `POST /api/v1/road-risk/predict` |

### P4 — Route Optimization Engine

**Purpose**: Find the **safest practical route** across real mapped roads, not just the shortest.

| Component | Detail |
|---|---|
| **Road Network** | OpenStreetMap via OSMnx + OSRM fallback routing |
| **Risk Scoring** | Live weather (Open-Meteo) + flood model + landslide susceptibility + IMD CAP warnings |
| **News Intelligence** | GDELT GKG + Google News RSS → hazard type detection → geographic matching → distance-from-route calculation |
| **Official Warnings** | IMD WIS2 CAP feed with point-in-polygon spatial matching against alert polygons |
| **NRSC/ISRO** | Bhuvan landslide hazard layer (when GeoJSON export available) |
| **Rail Integration** | Indian Railways API/GTFS for multimodal corridor planning |
| **Route Cost** | `Travel Time + Distance + Disaster Risk + Transfer Penalties` |
| **Graph Cache** | OSM graphs cached locally for repeated requests |
| **Endpoint** | `POST /api/v1/routes/optimize` (origin/destination as text) |

### P5 — Supply Chain & Logistics Management

**Purpose**: Manage shipments, predict shortages, and optimize warehouse allocation.

| Component | Detail |
|---|---|
| **Shipments** | Create, track, and risk-score shipments with P4 route integration |
| **Shortage Prediction** | Explainable baseline model (XGBoost-upgradeable) for supply shortage early warning |
| **Demand Prediction** | District-level demand forecasting for essential goods |
| **Warehouse Optimization** | Multi-depot stock allocation considering capacity and utilization |
| **P4 Integration** | Auto-fetches optimal route for origin→destination with risk scoring |
| **Endpoints** | `POST /api/v1/shipments`, `POST /api/v1/predictions/shortage`, `POST /api/v1/predictions/demand`, `POST /api/v1/warehouses/optimize` |

### P6 — Control Tower & Emergency Coordination

**Purpose**: Unified situational awareness, incident management, and scenario simulation.

| Component | Detail |
|---|---|
| **Incident Reporting** | Driver/citizen hazard reports with image upload |
| **AI Image Verification** | HuggingFace CLIP classification: LANDSLIDE · FLOOD · ROAD_BLOCKED · ACCIDENT · CLEAR |
| **EXIF Validation** | GPS metadata extraction + mismatch detection (>5 km = flagged) |
| **IMD Alerts** | Official IMD WIS2 CAP warnings fetched and parsed (base64 XML → structured alerts) |
| **What-If Simulation** | "What if NH-44 is blocked?" → calculates fleet delays, rerouting, affected shipments |
| **Control Tower Overview** | Aggregated KPIs: active incidents, disrupted corridors, fleet status, alert counts |
| **Real-Time Alerts** | WebSocket `/ws/alerts` for live push notifications |
| **Database** | SQLAlchemy (SQLite default, PostgreSQL-ready) |
| **Endpoints** | Full CRUD on incidents, alert evaluation, simulation, control-tower map state |

### Gemini AI Advisory Engine

**Purpose**: Generate human-readable tactical intelligence advisories for convoy dispatchers.

| Component | Detail |
|---|---|
| **Model** | Google Gemini 3.7 Flash via REST API |
| **Fallback Chain** | gemini-3.7-flash → gemini-3.6-flash → gemini-flash-latest |
| **System Prompt** | Specialized for NER disaster logistics with structured sections |
| **Deterministic Fallback** | Rule-based advisory when API is unavailable (always functional) |
| **Temperature** | 0.2 (factual, low creativity) |
| **Endpoint** | `POST /api/v1/ai/advisory` |

---

## API & Data Source Inventory

### Live External APIs Used

| # | API / Data Source | Provider | Cost | Auth | Used By |
|---|---|---|---|---|---|
| 1 | **Weather Forecast** | [Open-Meteo](https://open-meteo.com/) | Free | No key | P1, P2, P4 |
| 2 | **Flood Discharge Model** | [Open-Meteo Flood API](https://open-meteo.com/en/docs/flood-api) | Free | No key | P4 |
| 3 | **Elevation (GLO-90 DEM)** | [Open-Meteo Elevation](https://open-meteo.com/en/docs/elevation-api) | Free | No key | P1, P2 |
| 4 | **River Proximity** | [OSM Overpass API](https://overpass-api.de/) | Free | No key | P1 |
| 5 | **Road Network** | [OpenStreetMap / OSMnx](https://www.openstreetmap.org/) | Free | No key | P4 |
| 6 | **OSRM Routing** | [OSRM](http://router.project-osrm.org/) | Free | No key | P4 |
| 7 | **IMD Weather Warnings** | [IMD WIS2 CAP](https://wis2box.imd.gov.in/) | Free | No key | P4, P6 |
| 8 | **NRSC/ISRO Bhuvan** | [Bhuvan WMS](https://bhuvan-vec2.nrsc.gov.in/) | Free | Optional token | P4 |
| 9 | **NASA COOLR Landslides** | [NASA COOLR](https://coolr.sci.gsfc.nasa.gov/) | Free | No key | P2 |
| 10 | **Disaster News (GDELT)** | [GDELT Project](https://api.gdeltproject.org/) | Free | No key | P4 |
| 11 | **Google News RSS** | [Google News](https://news.google.com/) | Free | No key | P4 |
| 12 | **Land Cover** | [OSM Overpass](https://overpass-api.de/) | Free | No key | P2 |
| 13 | **Sentinel-2 Satellite** | [Copernicus CDSE](https://dataspace.copernicus.eu/) | Free tier | CDSE client ID/secret | P2 |
| 14 | **Gemini AI** | [Google Generative AI](https://ai.google.dev/) | Free tier | API key | Advisory |
| 15 | **CLIP Image Verification** | [HuggingFace Inference](https://huggingface.co/) | Free tier | HF token | P6 |
| 16 | **Indian Railways** | [Indian Rail API](https://indianrailapi.com/) | Freemium | API key | P4 |
| 17 | **Geocoding** | [Nominatim / OSM](https://nominatim.openstreetmap.org/) | Free | No key | P4 |

### Government Data Sources (Offline/Research)

| Source | Data | Status |
|---|---|---|
| CWC / India-WRIS | River water levels | Research pipeline (no live API) |
| NWIC River Network | River network geometry for proximity | Available when archive present |
| INDOFLOODS/IPED | Historical flood events | Training data for P1 ML model |
| GSI Landslide Inventory | Mapped landslide locations across India | Training data for P2 susceptibility model |
| Uttarakhand PWD MIS | Road status samples | Label feasibility research |
| ASDMA Reports | Assam disaster reports | Evidence discovery |
| Indian Road Accident Dataset | 20,000 accident records | Active training for P3 accident model |

---

## AI & Machine Learning Pipeline

### Models Currently Active

| Model | Algorithm | Training Data | Key Metrics | Purpose |
|---|---|---|---|---|
| **P1 Flood** | HistGradientBoosting + Platt Calibration | INDOFLOODS/IPED (chronological split) | ROC-AUC, PR-AUC, Brier Score, F1@0.35 | Flood probability per segment |
| **P2 Landslide** | Logistic Regression (upgradeable) | GSI India inventory + pseudo-absences | ROC-AUC, AP (geographic holdout) | Landslide susceptibility |
| **P3 Accident Risk** | HistGradientBoosting | 20K Indian accident records (14K/3K/3K) | ROC-AUC 0.518, F1 0.462, Brier 0.250 | Accident/traffic severity risk |
| **P3 Disruption** | Deterministic weighted fusion | Evidence-based (not supervised) | 94 unit tests passing | Road disruption likelihood |
| **P6 CLIP** | OpenAI CLIP ViT-B/32 | Pre-trained (zero-shot) | Multi-class classification | Incident image verification |
| **Gemini Advisory** | Google Gemini 3.7 Flash | N/A (LLM) | — | Natural language advisory generation |

### Training Philosophy

- **Chronological splits**: No future data leakage — train/validate/test ordered by date
- **Weak negatives explicitly labeled**: Missing flood records are never assumed to be non-floods
- **Heuristic fallback**: Every ML model degrades gracefully to a transparent rule-based fallback
- **Evidence completeness**: The system reports what data it had, not a false confidence from missing inputs

---

## Technology Stack

| Layer | Technology |
|---|---|
| **Backend Framework** | Python 3.11+ · FastAPI · Uvicorn |
| **ML/AI** | scikit-learn · HistGradientBoosting · joblib · Logistic Regression |
| **Generative AI** | Google Gemini 3.7 Flash (REST API) |
| **Computer Vision** | HuggingFace Transformers · OpenAI CLIP ViT-B/32 |
| **Geospatial** | OSMnx · NetworkX · OSRM · Shapely · Overpass API |
| **HTTP Client** | httpx (async-capable) |
| **Database** | SQLAlchemy + SQLite (production: PostgreSQL-ready) |
| **Real-time** | WebSocket (FastAPI native) |
| **Frontend** | Vanilla HTML/CSS/JS · Leaflet.js · Google Fonts (Inter, Outfit) |
| **Deployment** | Single unified server on port 8002 · `start.bat` launcher |

---

## User Roles & Access Model

### Desktop Application — Government Officials

The primary interface is a **desktop application** (Electron wrapper planned) restricted to authorized government personnel:

| Role | Access | Functions |
|---|---|---|
| **District Collector / DC** | Full dashboard | View all modules, approve rerouting, authorize emergency shipments |
| **Logistics Coordinator** | P4 + P5 + P6 | Route optimization, shipment management, warehouse allocation |
| **Emergency Response Officer** | P6 Control Tower | Incident verification, what-if simulation, alert management |
| **PWD / BRO Engineer** | P3 + P6 | Road risk assessment, incident reporting, maintenance planning |
| **Supply Chain Manager** | P5 | Shortage prediction, demand forecasting, inventory management |

### Mobile Application — Drivers & Field Personnel

A **mobile app prototype** (phone-based) is designed for:

| Feature | Detail |
|---|---|
| **Driver Login** | Authenticated driver portal with vehicle registration |
| **GPS Tracking** | Real-time vehicle location tracking (feeds into P6 control tower) |
| **Incident Reporting** | Photo + GPS + description → auto-verified by CLIP AI |
| **Route Guidance** | Receive optimized route from P4 with hazard warnings |
| **Emergency SOS** | One-tap alert to control tower with live location |

---

## How It All Works Together

### Scenario: Medicine Supply from Guwahati to Kohima during Monsoon

```
Step 1: Logistics Coordinator opens Pravah Desktop Dashboard
        → P6 Control Tower shows 3 active incidents on NH-36

Step 2: Creates a CRITICAL priority shipment (medicines, 2 trucks)
        → P5 logs shipment, checks Dimapur warehouse stock

Step 3: P4 Route Optimizer runs
        → Geocodes Guwahati (26.14°N, 91.74°E) → Kohima (25.67°N, 94.10°E)
        → Builds OSM road graph for NE India
        → Candidate Route A: NH-36 via Nagaon → Dimapur → Kohima (420 km)
        → Candidate Route B: NH-37 via Jorhat → Mokokchung → Kohima (520 km)

Step 4: Risk Engine scores both routes
        → P1: Flood probability 0.72 on Route A (heavy Brahmaputra flooding)
        → P2: Landslide probability 0.64 near Noney (Route A)
        → P3: Disruption score 0.81 (CRITICAL) for Route A
        → P3: Disruption score 0.35 (MODERATE) for Route B
        → IMD: Active RED alert for Karbi Anglong (Route A corridor)
        → GDELT: "Landslide blocks NH-36 near Haflong" published 4 hours ago
        → Route B selected despite being 100 km longer

Step 5: Gemini AI generates advisory
        → "CRITICAL: Avoid NH-36 corridor due to active landslide near Noney 
           and RED weather alert. Route B via Jorhat recommended. 
           Maintain satellite communication in Mokokchung hill section.
           Pre-stage at Jorhat warehouse if delays expected."

Step 6: Driver receives Route B on mobile app
        → GPS tracking begins
        → Driver reports "road waterlogged near Golaghat" with photo
        → P6 CLIP verifies: FLOOD (confidence 0.89)
        → EXIF check: GPS matches reported location ✓
        → Alert pushed to all officers via WebSocket

Step 7: What-If Simulation
        → "What if NH-37 also gets blocked near Mokokchung?"
        → Simulation: 2 trucks delayed 14 hours, Kohima medicine stock drops to critical
        → Recommendation: Pre-position stock at Dimapur warehouse
```

---

## Business Model & Deployment

### Phase 1: Government Deployment (Current)

- **Free for government**: Deployed as an internal tool for NER state governments
- **Data sovereignty**: All data stays on government infrastructure
- **Offline capability**: Frontend works with client-side simulation when backend is unreachable
- **Single server**: One `start.bat` command launches the entire platform

### Phase 2: Multi-State Expansion

- **Cloud deployment**: AWS/GCP with regional data residency
- **PostgreSQL migration**: From SQLite to production-grade database
- **Multi-tenant**: Each state gets its own dashboard with shared NER-wide intelligence

### Phase 3: National Scale

- **API marketplace**: Expose Pravah APIs to other disaster management platforms
- **NDMA integration**: Feed into the National Disaster Management Authority's systems
- **Indian Railway partnership**: Real-time rail disruption data for multimodal planning

---

## Future Roadmap

### Near-Term (Next 3 Months)

| Feature | Description |
|---|---|
| **Twilio WhatsApp Integration** | Citizens send disaster photos via WhatsApp → Twilio webhook → Google Sheet → Pravah DB → auto-verified incident |
| **Electron Desktop App** | Wrap the dashboard in Electron for restricted government distribution |
| **Driver Mobile App (Flutter)** | Production mobile app with GPS tracking, incident reporting, route guidance |
| **PostgreSQL Migration** | Production-ready database with proper migrations |

### Mid-Term (3-6 Months)

| Feature | Description |
|---|---|
| **Live Traffic Integration** | Google/Mappls traffic data for real-time congestion awareness |
| **Sentinel-1 SAR Flood Detection** | Radar-based flood extent mapping (works through clouds) |
| **BRO/PWD Road Status Feed** | Official real-time road closure data from Border Roads Organisation |
| **Push Notifications** | Firebase Cloud Messaging for mobile alerts |
| **Role-Based Authentication** | JWT-based auth with government SSO integration |
| **Multi-language Support** | UI in Assamese, Hindi, Manipuri, Mizo, Naga languages |

### Long-Term (6-12 Months)

| Feature | Description |
|---|---|
| **Drone Surveillance Integration** | Live drone feeds for road assessment in unreachable areas |
| **Predictive Maintenance** | Predict which roads/bridges will fail next based on historical patterns |
| **Blockchain Supply Chain** | Tamper-proof tracking for critical medical supplies |
| **Digital Twin** | Full NER road network digital twin with simulation capabilities |
| **ISRO Bhuvan Deep Integration** | Direct satellite data pipeline for terrain changes |

---

## Getting Started

### Prerequisites

- Python 3.11+
- pip (package manager)

### Quick Start

```bash
# Clone the repository
cd NER-Smart-Logistics

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Install all dependencies
pip install -r server/requirements.txt

# Launch the platform
start.bat
```

The platform launches at **http://127.0.0.1:8002** with:
- 📊 Web Dashboard at `/`
- 📖 API Documentation at `/docs`
- ❤️ Health Check at `/health`

### Environment Configuration

Copy `.env` and configure:

```env
# Google Gemini AI (for route advisories)
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-3.7-flash

# Copernicus Satellite (for Sentinel-2 data)
CDSE_CLIENT_ID=your_id
CDSE_CLIENT_SECRET=your_secret

# HuggingFace (for CLIP image verification)
HF_TOKEN=your_token

# Everything else works out of the box with free, no-auth APIs
```

---

## Project Structure

```
NER-Smart-Logistics/
│
├── server/                         # Unified backend
│   ├── unified_server.py           # FastAPI app integrating P1-P6 + Gemini AI
│   ├── p1_router.py                # P1 flood prediction endpoints
│   └── requirements.txt            # All Python dependencies
│
├── p1-flood/                       # Flood Intelligence Module
│   ├── src/
│   │   ├── fetch_rainfall.py       # Live rainfall from Open-Meteo
│   │   ├── fetch_terrain.py        # Live elevation + river from Open-Meteo + OSM
│   │   ├── flood_score.py          # Heuristic + ML scoring
│   │   ├── ml_model.py             # HistGradientBoosting training + inference
│   │   ├── build_training_table.py # INDOFLOODS/IPED training data pipeline
│   │   └── prepare_indofloods.py   # Historical flood event normalization
│   ├── models/                     # Trained model artifacts (.joblib)
│   └── data/                       # Cached API responses
│
├── p2-landslide/                   # Landslide Susceptibility Module
│   ├── app/
│   │   ├── main.py                 # FastAPI app
│   │   ├── scoring.py              # Risk engine (heuristic + trained model)
│   │   └── live_features.py        # Live data fetching pipeline
│   ├── build_gsi_susceptibility_dataset.py  # GSI inventory trainer
│   ├── train_model.py              # ML model training script
│   └── models/                     # Trained model artifacts (.pkl)
│
├── p3-road-risk/                   # Road Risk & Disruption Module
│   ├── p3_src/
│   │   ├── api.py                  # FastAPI routes
│   │   ├── hybrid.py               # Deterministic evidence fusion engine (v2)
│   │   ├── schemas.py              # Request/response models
│   │   ├── ml_pipeline/            # Accident model training pipeline
│   │   ├── data_pipeline/          # Data ingestion and normalization
│   │   ├── providers/              # Upstream P1/P2 probability adapters
│   │   └── satellite_cv/           # Sentinel research tools
│   ├── models/                     # Accident model + hybrid config
│   └── tests/                      # 94 unit tests
│
├── p4-path-optimization/           # Route Optimization Module
│   ├── p4_src/
│   │   ├── router.py               # RouteOptimizer engine
│   │   ├── graph_builder.py        # OSM road network graph construction
│   │   ├── risk_engine.py          # Multi-source risk scoring
│   │   ├── news_intelligence.py    # GDELT + Google News disaster detection
│   │   ├── official_data.py        # IMD CAP + NRSC/ISRO adapters
│   │   ├── transit.py              # Indian Railways integration
│   │   ├── geocoder.py             # Nominatim + India gazetteer
│   │   └── models.py               # Route request/response schemas
│   ├── cache/                      # OSM graph cache
│   └── preview.html                # Route visualization preview
│
├── p5-logistics/                   # Supply Chain Module
│   ├── p5_src/
│   │   ├── main.py                 # FastAPI app
│   │   ├── logistics.py            # Logistics service (41KB — full implementation)
│   │   ├── schemas.py              # Shipment, demand, shortage schemas
│   │   └── p4_client.py            # P4 route integration client
│   └── tests/
│
├── p6-control-tower/               # Control Tower Module
│   ├── alerts/
│   │   ├── router.py               # Alert evaluation endpoints
│   │   └── imd.py                  # Official IMD CAP warning parser
│   ├── incidents/
│   │   ├── router.py               # Incident CRUD + driver reporting
│   │   └── verify.py               # CLIP + EXIF image verification
│   ├── simulation/
│   │   ├── engine.py               # What-if impact simulation engine
│   │   ├── clients.py              # P4/P5 HTTP clients for simulation
│   │   └── router.py               # Simulation API endpoint
│   ├── p6_src/
│   │   ├── tower.py                # Control tower aggregation
│   │   ├── database.py             # SQLAlchemy engine management
│   │   ├── orm.py                  # Database models
│   │   ├── hub.py                  # WebSocket connection hub
│   │   └── config.py               # P6 configuration
│   └── data/                       # SQLite DB + snapshots
│
├── shared/                         # Cross-module utilities
│   ├── gemini_service.py           # Gemini AI integration
│   └── schemas/                    # Shared data schemas
│
├── Frontend/                       # Web Dashboard
│   ├── index.html                  # 172KB single-page application
│   ├── css/                        # Stylesheets
│   ├── js/                         # JavaScript modules
│   └── Frontend_Few_Parts/         # Component screenshots
│
├── docs/                           # Documentation
│   ├── api-contracts.md            # API schema contracts
│   ├── api_requirements.md         # Integration requirements
│   └── component_audit.md          # Audit and validation report
│
├── .env                            # Environment configuration
├── start.bat                       # One-click launcher (Windows)
└── start_all.sh                    # One-click launcher (Linux/Mac)
```

---

## License

Built for **Smart India Hackathon 2026 (SIH 26002)** — Problem Statement: AI-Powered Smart Logistics & Accessibility Intelligence Platform for the North Eastern Region.

---

> **Pravah** — *Because in Northeast India, the difference between a medicine reaching a patient and a supply shortage isn't just a logistics problem. It's a matter of life and death. And we refuse to let terrain win.*
]]>
