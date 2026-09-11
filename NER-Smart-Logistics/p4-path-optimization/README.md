# 🚨 Northeast India Disaster-Aware Smart Logistics

A **risk-aware route optimization system** focused on Northeast India. It finds practical, mapped travel routes and considers **weather, flood risk, landslide susceptibility, official warnings, and disaster news** before selecting the best route.

## ✨ Key Features

- 🛣️ Real mapped-road routing using **OpenStreetMap**
- 🧭 Risk-aware shortest/travelable route selection
- ⛰️ Landslide susceptibility analysis
- 🌊 Flood-risk analysis
- 🌦️ Weather conditions and rainfall data
- 🇮🇳 IMD weather/warning integration
- 📰 Disaster-news intelligence using **GDELT + Google News RSS**
- 📍 Geographic matching of news to the route
- 🔄 Alternative route support
- 💾 OSM graph caching for faster repeated requests
- 🚢 Multimodal architecture for road/ferry/rail extensions
- ⚡ FastAPI backend with REST APIs
- 🗺️ HTML preview frontend for testing/demo

---

## 🧠 How It Works

```text
Origin + Destination
        │
        ▼
     Geocoding
        │
        ▼
Real Travel Network
(OSM / OSRM fallback)
        │
        ▼
Candidate Routes
        │
        ├── Weather
        ├── Flood Risk
        ├── Landslide Risk
        ├── IMD Warnings
        └── Disaster News
                │
                ▼
          Risk Scoring
                │
                ▼
       Route Optimization
                │
                ▼
     Best Practical Route
```

The system does **not** simply choose the shortest geographic path.

```text
Route Cost =
Travel Time
+ Distance
+ Disaster Risk
+ Transfer Penalties
```

A slightly longer route can therefore be selected if the shortest route passes through a significantly higher-risk area.

---

## 📰 Disaster News Intelligence

News is location-aware rather than simply searching for keywords.

```text
GDELT + Google News
        │
        ▼
Hazard Detection
        │
        ▼
Location Extraction
        │
        ▼
Geographic Matching
        │
        ▼
Distance from Route
        │
        ▼
News Risk
```

Supported hazards include:

- Landslide
- Flood / Flash Flood
- Heavy Rain
- Cloudburst
- Road Closure
- Highway Blockage
- Bridge Damage
- Waterlogging
- Road Washed Away
- Other transportation disruptions

Example:

```text
"Flood reported in Dehradun"
          ↓
     Dehradun
          ↓
   Geographical match
          ↓
Relevant only if near the selected route
```

---

## 🌐 Data Sources

| Data | Source |
|---|---|
| Roads / Transport Network | OpenStreetMap |
| Road Routing | OSRM |
| OSM Network Queries | Overpass API |
| Weather | Open-Meteo |
| Flood Model | Open-Meteo Flood API |
| Weather Warnings | IMD / configured official sources |
| Disaster News | GDELT + Google News RSS |

> Data availability and freshness depend on the respective provider.

---

## 🗂️ Project Structure

```text
p4-routing/
│
├── src/
│   ├── main.py
│   ├── router.py
│   ├── graph_builder.py
│   ├── risk_engine.py
│   ├── news_intelligence.py
│   ├── official_data.py
│   ├── geocoder.py
│   ├── models.py
│   └── config.py
│
├── data/
│   └── graph_cache/
│
├── tests/
│
├── preview.html
├── requirements.txt
└── README.md
```

---

## 🚀 Installation

### 1. Create virtual environment

```bash
python -m venv venv
```

### 2. Activate it — Windows

```bash
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Start backend

```bash
python -m uvicorn src.main:app --reload --host 127.0.0.1 --port 8001
```

### 5. Open

```text
preview.html
```

---

## 🔌 Main APIs

### Health Check

```http
GET /health
```

### Route Optimization

```http
POST /api/routes/optimize
```

Example:

```json
{
  "origin": "Guwahati",
  "destination": "Shillong"
}
```

### Data Sources

```http
GET /api/v1/data-sources
```

### News Status

```http
GET /api/v1/news/status
```

---

## 🛣️ Routing Logic

The system prefers **actual mapped infrastructure** instead of straight-line distance.

```text
          ❌ Straight line
A ───────────────────────── B

          ✅ Travel network
A ────┐
      └──────┐
             ├──────── B
      ┌──────┘
A ────┘
```

This helps prevent routes through buildings, inaccessible terrain, rivers, forests, etc., where no mapped road exists.

---

## ⚠️ Important Limitations

This system should be described as **risk-aware decision support**, not a guaranteed real-time road-closure system.

- 🚧 Road closures are not guaranteed to be real-time.
- 🚦 Live traffic is not currently included.
- ⛰️ Landslide susceptibility ≠ confirmed active landslide.
- 🌊 Flood model data ≠ confirmed road flooding.
- 🚆 Railway passenger availability is not fully implemented.
- ⛴️ Mapped ferry infrastructure does not guarantee today's operation.
- 📰 News depends on source coverage and availability.

---

## 🎯 Primary Use Case

The project is primarily designed for **Northeast India**, where mountainous terrain, heavy rainfall, landslides and flooding can significantly affect transportation.

Example:

```text
Guwahati → Shillong
        │
        ▼
Check road network
        │
        ▼
Check weather
        │
        ▼
Check flood / landslide risk
        │
        ▼
Check IMD warnings
        │
        ▼
Check recent disaster news
        │
        ▼
Select safer practical route
```

---

## 🔮 Future Extensions

- 🚆 Live Indian Railways integration
- 🚧 Verified government road-closure feeds
- 🚦 Live traffic data
- ⛴️ Live ferry schedules/status
- 🛰️ Near-real-time satellite landslide detection
- 🌊 Real-time river/water-level observations
- 🤖 More advanced multi-objective optimization

---

## 🏆 Project Goal

> **Find the best practical route, not merely the shortest route, by combining real transportation infrastructure with environmental and disaster intelligence.**

**Focus:** Northeast India Disaster-Aware Smart Logistics  
**Backend:** Python + FastAPI  
**Routing:** OSM + OSRM + NetworkX  
**Intelligence:** Weather + Flood + Landslide + IMD + News
