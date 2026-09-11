"""
NER Smart Logistics — Unified Backend Server
=============================================
Integrates all P1–P6 modules into a single FastAPI application.
Run: python -m uvicorn server.unified_server:app --host 127.0.0.1 --port 8002 --reload
"""
from __future__ import annotations

import importlib
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# ---------------------------------------------------------------------------
# PATH SETUP — make every module importable
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = PROJECT_ROOT / "Frontend"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)
logger = logging.getLogger("pravah-unified")

# ---------------------------------------------------------------------------
# MODULE STATUS TRACKER
# ---------------------------------------------------------------------------
module_status = {
    "p1_flood": "unavailable",
    "p2_landslide": "unavailable",
    "p3_road_risk": "unavailable",
    "p4_routing": "unavailable",
    "p5_logistics": "unavailable",
    "p6_control_tower": "unavailable",
}


# ===== P1 — Flood Intelligence =============================================
p1_router = None
try:
    p1_path = str(PROJECT_ROOT / "server")
    if p1_path not in sys.path:
        sys.path.insert(0, p1_path)
    # Also add p1-flood/src for flood_score imports
    p1_src = str(PROJECT_ROOT / "p1-flood" / "src")
    if p1_src not in sys.path:
        sys.path.insert(0, p1_src)
    from p1_router import p1_router
    module_status["p1_flood"] = "available"
    logger.info("✓ P1 Flood Intelligence loaded.")
except Exception as exc:
    logger.warning("✗ P1 Flood: %s", exc)


# ===== P2 — Landslide Intelligence =========================================
p2_app = None
try:
    p2_root = str(PROJECT_ROOT / "p2-landslide")
    if p2_root not in sys.path:
        sys.path.insert(0, p2_root)
    from app.main import app as p2_app
    module_status["p2_landslide"] = "available"
    logger.info("✓ P2 Landslide Intelligence loaded.")
except Exception as exc:
    logger.warning("✗ P2 Landslide: %s", exc)


# ===== P3 — Road Risk & Accessibility ======================================
p3_router_raw = None
try:
    p3_root = str(PROJECT_ROOT / "p3-road-risk")
    if p3_root not in sys.path:
        sys.path.insert(0, p3_root)
    from p3_src.api import router as p3_router_raw
    module_status["p3_road_risk"] = "available"
    logger.info("✓ P3 Road Risk loaded.")
except Exception as exc:
    logger.warning("✗ P3 Road Risk: %s", exc)


# ===== P4 — Route Optimization =============================================
RouteOptimizer = None
RouteRequest = None
RouteResponse = None
p4_data_fns = {}
p4_optimizer = None

try:
    p4_root = str(PROJECT_ROOT / "p4-path-optimization")
    if p4_root not in sys.path:
        sys.path.insert(0, p4_root)
    from p4_src.router import RouteOptimizer
    from p4_src.models import RouteRequest, RouteResponse
    from p4_src.official_data import nrsc_metadata, fetch_imd_cap_alerts
    from p4_src.news_intelligence import fetch_live_disaster_news, news_status
    from p4_src.transit import railway_feed_status, fetch_train_schedule
    p4_data_fns = {
        "nrsc_metadata": nrsc_metadata,
        "fetch_imd_cap_alerts": fetch_imd_cap_alerts,
        "fetch_live_disaster_news": fetch_live_disaster_news,
        "news_status": news_status,
        "railway_feed_status": railway_feed_status,
        "fetch_train_schedule": fetch_train_schedule,
    }
    module_status["p4_routing"] = "available"
    logger.info("✓ P4 Route Optimization loaded.")
except Exception as exc:
    logger.warning("✗ P4 Route Optimization: %s", exc)


# ===== P5 — Logistics & Supply Chain =======================================
p5_app = None
try:
    p5_root = str(PROJECT_ROOT / "p5-logistics")
    if p5_root not in sys.path:
        sys.path.insert(0, p5_root)
    from p5_src.main import app as p5_app
    module_status["p5_logistics"] = "available"
    logger.info("✓ P5 Logistics loaded.")
except Exception as exc:
    logger.warning("✗ P5 Logistics: %s", exc)


# ===== P6 — Control Tower ==================================================
p6_routers = {}
p6_engine_fn = None
p6_hub = None
p6_db_url_fn = None

try:
    p6_root = str(PROJECT_ROOT / "p6-control-tower")
    if p6_root not in sys.path:
        sys.path.insert(0, p6_root)

    from alerts.router import router as p6_alerts_router
    from incidents.router import router as p6_incidents_router
    from simulation.router import router as p6_simulation_router
    from p6_src.tower import router as p6_tower_router
    from p6_src.database import get_engine as p6_get_engine
    from p6_src.hub import hub as p6_hub_obj
    from p6_src.config import database_url as p6_database_url

    p6_routers = {
        "alerts": p6_alerts_router,
        "incidents": p6_incidents_router,
        "simulation": p6_simulation_router,
        "tower": p6_tower_router,
    }
    p6_engine_fn = p6_get_engine
    p6_hub = p6_hub_obj
    p6_db_url_fn = p6_database_url
    module_status["p6_control_tower"] = "available"
    logger.info("✓ P6 Control Tower loaded.")
except Exception as exc:
    logger.warning("✗ P6 Control Tower: %s", exc)


# ---------------------------------------------------------------------------
# LIFESPAN
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app):
    global p4_optimizer

    # Init P4
    if RouteOptimizer is not None:
        try:
            p4_optimizer = RouteOptimizer()
            logger.info("P4 RouteOptimizer ready (graphs loaded lazily).")
        except Exception as e:
            logger.warning("P4 RouteOptimizer init failed: %s", e)

    # Init P6 database
    if p6_engine_fn is not None:
        try:
            p6_engine_fn()
            logger.info("P6 database ready: %s", p6_db_url_fn() if p6_db_url_fn else "?")
        except Exception as e:
            logger.warning("P6 database init failed: %s", e)

    logger.info("═══════════════════════════════════════════════════")
    logger.info("  Pravah Unified Server ready on port 8002")
    logger.info("  Module status: %s", module_status)
    logger.info("═══════════════════════════════════════════════════")
    yield


# ---------------------------------------------------------------------------
# APPLICATION
# ---------------------------------------------------------------------------
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(
    title="Pravah — Unified NER Smart Logistics Platform",
    version="3.0.0",
    description=(
        "Unified backend integrating P1 Flood, P2 Landslide, P3 Road Risk, "
        "P4 Route Optimization, P5 Logistics, P6 Control Tower."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# UNIFIED HEALTH ENDPOINT
# ---------------------------------------------------------------------------
@app.get("/health")
async def unified_health():
    return {
        "status": "ok",
        "server": "pravah-unified",
        "version": "3.0.0",
        "modules": module_status,
    }


# ===== MOUNT P1 ============================================================
if p1_router is not None:
    app.include_router(p1_router)


# ===== MOUNT P2 ============================================================
if p2_app is not None:
    # Re-register P2's routes on the unified app
    from starlette.routing import Route as StarletteRoute
    for route in p2_app.routes:
        if hasattr(route, "methods") and hasattr(route, "path"):
            app.routes.append(route)


# ===== MOUNT P3 ============================================================
if p3_router_raw is not None:
    @app.post("/api/v1/road-risk/predict")
    async def unified_p3_predict(request: Request):
        try:
            body = await request.json()
        except Exception:
            body = {}
        road_id = str(body.get("road_id", "NH-13"))
        flood_prob = float(body.get("flood_probability", body.get("flood_risk", 0.32)))
        landslide_prob = float(body.get("landslide_probability", body.get("landslide_risk", 0.44)))
        active_incidents = int(body.get("active_incidents", body.get("active_incident_count", 1)))
        max_severity = int(body.get("max_incident_severity", 3))

        from datetime import datetime, timezone
        from p3_src.schemas import RoadSegment, HazardContext, Incident
        from p3_src.services.risk_engine import RiskEngine

        engine = RiskEngine()
        roads = [RoadSegment(road_id=road_id)]
        hazards = [HazardContext(road_id=road_id, flood_probability=min(1.0, max(0.0, flood_prob)), landslide_probability=min(1.0, max(0.0, landslide_prob)))]
        incidents = []
        if active_incidents > 0:
            incidents.append(Incident(
                incident_id="INC-01",
                road_id=road_id,
                type="hazard",
                severity=max(1, min(5, max_severity)),
                status="active",
                latitude=float(body.get("latitude", 26.15)),
                longitude=float(body.get("longitude", 91.74)),
                reported_at=datetime.now(timezone.utc),
            ))

        analyzed = engine.analyze(roads, hazards, incidents)[0]
        return {
            "road_id": road_id,
            "disruption_likelihood_score": round(analyzed.disruption_probability, 4),
            "disruption_probability": round(analyzed.disruption_probability, 4),
            "accessibility_score": round(analyzed.accessibility_score, 2),
            "risk_level": analyzed.risk_level.upper(),
            "recommended_status": analyzed.recommended_status,
            "confidence": analyzed.confidence or 0.85,
            "factors": {
                "flood_probability": flood_prob,
                "landslide_probability": landslide_prob,
                "active_incident_count": active_incidents,
                "max_incident_severity": max_severity,
            },
            "explanation": analyzed.explanation,
            "model_version": engine.model_version,
        }

    app.include_router(p3_router_raw, prefix="/api/v1/road-risk")


# ===== MOUNT P4 ============================================================
if RouteOptimizer is not None:

    @app.get("/api/v1/data-sources")
    async def p4_data_sources():
        return {
            "sources": {
                "OpenStreetMap roads": {"enabled": True, "role": "travel network"},
                "Indian Railways": p4_data_fns["railway_feed_status"](),
                "IMD warnings": {"enabled": True, "role": "public CAP warnings"},
                "NRSC/ISRO landslide": p4_data_fns["nrsc_metadata"](),
                "IWAI/OSM ferries": {"enabled": True, "role": "OSM route=ferry + official NW-2 context"},
                "Live disaster news": p4_data_fns["news_status"](),
            }
        }

    @app.get("/api/v1/rail/train/{train_number}")
    async def p4_rail_train(train_number: str):
        return p4_data_fns["fetch_train_schedule"](train_number)

    @app.get("/api/v1/alerts/imd")
    async def p4_imd_alerts():
        alerts = p4_data_fns["fetch_imd_cap_alerts"]()
        return {"count": len(alerts), "alerts": alerts}

    @app.get("/api/v1/news/status")
    async def p4_news_status():
        return p4_data_fns["news_status"]()

    @app.get("/api/v1/news/route")
    async def p4_route_news(origin: str, destination: str):
        from p4_src.geocoder import geocode
        o = geocode(origin)
        d = geocode(destination)
        events = p4_data_fns["fetch_live_disaster_news"](origin, destination, o, d)
        return {
            "origin": origin,
            "destination": destination,
            "count": len(events),
            "events": events,
        }

    @app.get("/api/v1/news/disasters")
    async def p4_disaster_news(place: str = "Northeast India"):
        from p4_src.geocoder import geocode
        coords = geocode(place)
        events = p4_data_fns["fetch_live_disaster_news"](place, place, coords, coords)
        return {"place": place, "count": len(events), "events": events}

    @app.post("/api/v1/routes/optimize")
    async def p4_optimize_route(request: Request):
        try:
            body = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Invalid JSON"})
        try:
            req = RouteRequest.model_validate(body)
            if p4_optimizer is None:
                raise RuntimeError("P4 Optimizer not ready")
            return p4_optimizer.optimize(req)
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)})
        except Exception as exc:
            logger.exception("Route optimisation failed")
            return JSONResponse(status_code=500, content={"error": str(exc)})

    # Aliases for frontend compatibility
    @app.post("/api/routes/optimize")
    async def p4_alias1(request: Request):
        return await p4_optimize_route(request)

    @app.post("/api/v1/optimize")
    async def p4_alias2(request: Request):
        return await p4_optimize_route(request)

    @app.get("/api/v1/reverse-geocode")
    async def api_reverse_geocode(lat: float, lng: float):
        from p4_src.geocoder import reverse_geocode
        name = reverse_geocode(lat, lng)
        return {"latitude": lat, "longitude": lng, "name": name, "status": "success"}

    @app.get("/api/v1/geocode")
    async def api_geocode(q: str):
        from p4_src.geocoder import geocode
        try:
            coords = geocode(q)
            return {"name": q, "latitude": coords[0], "longitude": coords[1], "status": "success"}
        except Exception as e:
            return JSONResponse(status_code=404, content={"error": str(e), "status": "not_found"})


# ===== MOUNT P5 ============================================================
if p5_app is not None:
    for route in p5_app.routes:
        if hasattr(route, "methods") and hasattr(route, "path"):
            app.routes.append(route)


# ===== MOUNT P6 ============================================================
if p6_routers:
    for name, r in p6_routers.items():
        app.include_router(r)

    if p6_hub is not None:
        @app.websocket("/ws/alerts")
        async def ws_alerts(ws: WebSocket):
            await p6_hub.connect(ws)
            try:
                while True:
                    await ws.receive_text()
            except WebSocketDisconnect:
                p6_hub.disconnect(ws)


# ---------------------------------------------------------------------------
# SERVE FRONTEND AS STATIC FILES
# ---------------------------------------------------------------------------
if FRONTEND_DIR.exists():
    if (FRONTEND_DIR / "css").exists():
        app.mount("/css", StaticFiles(directory=str(FRONTEND_DIR / "css")), name="css")
    if (FRONTEND_DIR / "js").exists():
        app.mount("/js", StaticFiles(directory=str(FRONTEND_DIR / "js")), name="js")

    @app.get("/")
    async def serve_index():
        index_file = FRONTEND_DIR / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return {"message": "Pravah Backend Active", "docs": "/docs"}

    @app.get("/index.html")
    async def serve_index_html():
        return await serve_index()
else:
    @app.get("/")
    async def root():
        return {"message": "Pravah Unified Backend Active", "docs": "/docs", "health": "/health"}


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8002,
    )
