"""FastAPI application for NER Smart Logistics routing."""
from __future__ import annotations
import logging
from contextlib import asynccontextmanager
from typing import Optional
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from p4_src.models import RouteRequest, RouteResponse
from p4_src.router import RouteOptimizer
from p4_src.official_data import nrsc_metadata, fetch_imd_cap_alerts
from p4_src.news_intelligence import fetch_live_disaster_news, news_status
from p4_src.transit import railway_feed_status, fetch_train_schedule

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(name)s — %(message)s")
logger=logging.getLogger("pravah-routing")
optimizer: Optional[RouteOptimizer]=None

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = (BASE_DIR / "frontend") if (BASE_DIR / "frontend").exists() else (BASE_DIR.parent / "frontend")

@asynccontextmanager
async def lifespan(app: FastAPI):
    global optimizer
    optimizer=RouteOptimizer()
    logger.info("Ready. Pravah real OSM graphs are loaded lazily per requested corridor.")
    yield

app=FastAPI(title="Pravah — Intelligent Multi-Hazard Logistics & Route Optimization API",version="2.4.0",
    description="Pravah: Autonomous corridor routing on real OpenStreetMap geometry with live multi-hazard risk engine.",lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_methods=["*"],allow_headers=["*"])

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
    if (FRONTEND_DIR / "css").exists():
        app.mount("/css", StaticFiles(directory=str(FRONTEND_DIR / "css")), name="css")
    if (FRONTEND_DIR / "js").exists():
        app.mount("/js", StaticFiles(directory=str(FRONTEND_DIR / "js")), name="js")
    if (FRONTEND_DIR / "modules").exists():
        app.mount("/modules", StaticFiles(directory=str(FRONTEND_DIR / "modules")), name="modules")

@app.get("/")
async def root_index():
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "Pravah Backend Active", "docs": "/docs"}

@app.get("/index.html")
async def index_html():
    return await root_index()

@app.get("/health")
async def health():
    return {"status":"ok","real_network":"OpenStreetMap","graph_loaded": bool(optimizer and optimizer.graph),"nodes": optimizer.graph.number_of_nodes() if optimizer and optimizer.graph else 0,"edges": optimizer.graph.number_of_edges() if optimizer and optimizer.graph else 0}

@app.get("/api/v1/data-sources")
async def data_sources():
    return {"sources": {"OpenStreetMap roads": {"enabled": True, "role": "travel network"}, "Indian Railways": railway_feed_status(), "IMD warnings": {"enabled": True, "role": "public CAP warnings"}, "NRSC/ISRO landslide": nrsc_metadata(), "IWAI/OSM ferries": {"enabled": True, "role": "OSM route=ferry + official NW-2 context"}, "Live disaster news": news_status()}}

@app.get("/api/v1/rail/train/{train_number}")
async def rail_train(train_number: str):
    return fetch_train_schedule(train_number)

@app.get("/api/v1/alerts/imd")
async def imd_alerts():
    alerts = fetch_imd_cap_alerts()
    return {"count": len(alerts), "alerts": alerts}

@app.get("/api/v1/news/status")
async def news_feed_status():
    return news_status()

@app.get("/api/v1/news/route")
async def route_news(origin: str, destination: str):
    from p4_src.geocoder import geocode
    o=geocode(origin); d=geocode(destination)
    events=fetch_live_disaster_news(origin,destination,o,d)
    return {"origin":origin,"destination":destination,"count":len(events),"geolocated_events":sum(1 for e in events if e.get("geolocated")),"events":events}

@app.get("/api/v1/news/disasters")
async def disaster_news(place: str = "Northeast India"):
    # Standalone inspection endpoint. Route optimization performs its own
    # origin/destination anchored searches and spatial proximity scoring.
    from p4_src.geocoder import geocode
    coords = geocode(place)
    events = fetch_live_disaster_news(place, place, coords, coords)
    return {"place": place, "count": len(events), "events": events}

@app.post("/api/v1/routes/optimize",response_model=RouteResponse)
async def optimize_route(request: Request):
    try: body=await request.json()
    except Exception: return JSONResponse(status_code=400,content={"error":"Invalid or empty JSON request body"})
    try:
        req=RouteRequest.model_validate(body)
        if optimizer is None: raise RuntimeError("Optimizer is not ready")
        return optimizer.optimize(req)
    except ValueError as exc: return JSONResponse(status_code=400,content={"error":str(exc)})
    except Exception as exc:
        logger.exception("Route optimisation failed")
        return JSONResponse(status_code=500,content={"error":str(exc)})

@app.post("/api/routes/optimize",response_model=RouteResponse)
@app.post("/api/v1/optimize",response_model=RouteResponse)
async def optimize_route_alias(request: Request): return await optimize_route(request)
