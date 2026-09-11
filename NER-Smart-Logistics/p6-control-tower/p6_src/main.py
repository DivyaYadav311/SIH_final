"""FastAPI application for NER Smart Logistics — P6 Control Tower."""
from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from alerts.router import router as alerts_router
from incidents.router import router as incidents_router
from simulation.router import router as simulation_router
from p6_src.config import database_url, hf_token, p3_base_url, p4_base_url, p5_base_url
from p6_src.database import get_engine
from p6_src.hub import hub
from p6_src.tower import router as tower_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(name)s — %(message)s")
logger = logging.getLogger("p6-control-tower")


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_engine()
    logger.info("P6 Control Tower ready. database=%s", database_url())
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="NER Smart Logistics — P6 Control Tower",
        version="1.0.0",
        description="Incidents, image verification, alerts, what-if simulation, and control-tower aggregation.",
        lifespan=lifespan,
    )
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    app.include_router(incidents_router)
    app.include_router(alerts_router)
    app.include_router(simulation_router)
    app.include_router(tower_router)

    @app.get("/health")
    async def health():
        get_engine()
        return {
            "status": "ok",
            "module": "p6-control-tower",
            "database": "configured",
            "hf_token_configured": bool(hf_token()),
        }

    @app.get("/api/v1/data-sources")
    async def data_sources():
        return {
            "sources": {
                "IMD CAP": {
                    "enabled": True,
                    "url": "https://wis2box.imd.gov.in/oapi/collections/messages/items",
                    "role": "official weather warnings",
                },
                "Hugging Face CLIP": {
                    "enabled": bool(hf_token()),
                    "role": "incident image verification",
                    "fallback": "local CLIP via transformers",
                },
                "P3 road risk": {"configured": bool(p3_base_url()), "role": "alert evaluate inputs"},
                "P4 routing": {"configured": bool(p4_base_url()), "role": "what-if alternative routes"},
                "P5 logistics": {"configured": bool(p5_base_url()), "role": "shipments for simulation"},
                "P6 snapshots": {"enabled": True, "role": "schema-faithful development records until P4/P5 HTTP is live"},
            }
        }

    @app.websocket("/ws/alerts")
    async def ws_alerts(ws: WebSocket):
        await hub.connect(ws)
        try:
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            hub.disconnect(ws)

    ui_dir = ROOT / "frontend-test"
    dashboard = ui_dir / "index.html"

    @app.get("/dashboard")
    async def dashboard_page():
        if not dashboard.is_file():
            return {"error": "frontend-test/index.html is missing"}
        return FileResponse(dashboard)

    if ui_dir.is_dir():
        app.mount("/ui", StaticFiles(directory=str(ui_dir), html=True), name="ui")

    return app


app = create_app()
