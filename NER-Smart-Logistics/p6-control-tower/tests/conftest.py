from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def isolate_external_http(monkeypatch):
    monkeypatch.setattr("alerts.imd.fetch_imd_cap_alerts", lambda limit=100: [])
    monkeypatch.setattr("p6_src.tower.fetch_imd_cap_alerts", lambda limit=100: [], raising=False)
    monkeypatch.setattr("simulation.clients.fetch_p5_shipments", lambda: None)
    monkeypatch.setattr("simulation.clients.request_p4_route", lambda *args, **kwargs: None)
    monkeypatch.setattr("simulation.clients.request_p4_alternative", lambda origin, destination: None)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'p6.db').as_posix()}")
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("P4_BASE_URL", raising=False)
    monkeypatch.delenv("P5_BASE_URL", raising=False)
    from p6_src.database import reset_engine

    reset_engine()
    from p6_src.main import create_app

    app = create_app()
    with TestClient(app) as c:
        yield c
    reset_engine()
