# Pravah — Disaster-Aware Smart Logistics & Route Optimization Platform

> **Pravah — Safer Journeys. Stronger North East.**  
> Smart India Hackathon (SIH 26002)

Pravah is a high-performance, enterprise-grade, **light-themed** web application designed for disaster-aware supply chain logistics, multi-hazard intelligence, and route optimization across Northeast India.

---

## 🌟 Key Highlights & Features

1. **Light-Themed Professional UI**:
   - Modern, high-contrast, clean government & control-room aesthetic.
   - Powered by Google Fonts `Inter` & `Outfit`, refined glassmorphic cards, subtle elevation shadows, and responsive grid layouts.
   - Full Disaster Mode toggle with emergency high-contrast indicators.

2. **Connected Multi-Hazard Prediction Pipeline (P1 ➔ P2 ➔ P3 ➔ P4)**:
   - **P1 Flood Inundation Engine**: Real-time evaluation based on rainfall, digital elevation model (DEM), and river proximity.
   - **P2 Landslide Susceptibility Engine**: Slope angle analysis, 3-day cumulative precipitation, and Sentinel-2 satellite context.
   - **P3 Road Disruption & Accessibility**: Synthesizes flood and landslide predictions with active field incident reports to generate disruption risk and road accessibility scores.
   - **P4 Route Optimizer**: Computes safest vs fastest practical routes over real OpenStreetMap road infrastructure.

3. **Complete Integrated Modules & Tabs**:
   - **Path Optimization**: Centerpiece view matching the operational dashboard with route planner, Leaflet map, layer controls, AI model ribbon, telemetry tiles, and disaster news.
   - **Overview**: Regional macro control tower with live KPI cards and corridor vulnerability matrix.
   - **Risk Intelligence**: Interactive testing sandbox for P1, P2, and P3 models.
   - **Logistics (P5)**: Critical shipment management, supply shortage prediction, and multi-depot warehouse stock optimizer.
   - **Incidents & Alerts (P6)**: Citizen & driver hazard reporting with AI CLIP photo verification.
   - **What-If Simulation**: Scenario disruption engine calculating fleet delays and detour suggestions.

---

## 🚀 How to Run

### Option 1: Direct Browser
Simply double-click or open `index.html` in any modern web browser (Chrome, Edge, Firefox, Safari).

### Option 2: Local HTTP Server
Run any lightweight static server:
```bash
# Python
python -m http.server 3000

# Node.js
npx serve .
```
Then navigate to `http://localhost:3000`.

---

## 🔌 Backend Integration

Pravah communicates with the `NER-Smart-Logistics` microservices:

| Module | Default Port | Role | Endpoint Sample |
|---|---|---|---|
| **P4 Routing** | `http://127.0.0.1:8001` | OSM Route Optimization | `POST /api/v1/routes/optimize` |
| **P6 Control Tower** | `http://127.0.0.1:8006` | Incidents & What-If Simulation | `GET /api/v1/control-tower/overview` |
| **P5 Logistics** | `http://127.0.0.1:8000` | Shipments & Shortages | `POST /api/v1/predictions/shortage` |
| **P2 Landslide** | `http://127.0.0.1:8002` | Live Landslide Prediction | `POST /api/v1/predictions/landslide` |
| **P3 Road Risk** | `http://127.0.0.1:8003` | Road Risk Engine | `POST /predict` |

### Dual-Engine Resiliency
If any backend service is not yet running, Pravah automatically activates its client-side simulation engine, ensuring 100% functionality and seamless demonstration at all times without crashing or blocking.
