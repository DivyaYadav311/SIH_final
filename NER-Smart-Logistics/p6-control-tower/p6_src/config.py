"""Runtime configuration. Optional upstream URLs are never required to boot."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
_UNIFIED_DATA = ROOT.parent / "data" / "p6_control_tower"
_LOCAL_DATA = ROOT / "data"
DATA_DIR = _UNIFIED_DATA if _UNIFIED_DATA.exists() else _LOCAL_DATA
SNAPSHOT_DIR = DATA_DIR / "snapshots"

load_dotenv(ROOT / ".env")
load_dotenv(ROOT.parent / ".env")

RISK_LEVELS = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
INCIDENT_STATUSES = (
    "UNDER_VERIFICATION",
    "VERIFIED",
    "REJECTED",
    "RESOLVED",
)
CLIP_LABELS = ("LANDSLIDE", "FLOOD", "ROAD_BLOCKED", "ACCIDENT", "CLEAR")
EXIF_MISMATCH_KM = float(os.getenv("P6_EXIF_MISMATCH_KM", "5.0"))
HF_CLIP_MODEL = os.getenv("HF_CLIP_MODEL", "openai/clip-vit-base-patch32")
IMD_CAP_MESSAGES_URL = os.getenv(
    "IMD_CAP_MESSAGES_URL",
    "https://wis2box.imd.gov.in/oapi/collections/messages/items",
)
IMD_CAP_META = "urn:wmo:md:in-imd:cap_alerts"


def database_url() -> str:
    override = os.getenv("DATABASE_URL") or os.getenv("P6_DATABASE_URL")
    if override:
        return override
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{(DATA_DIR / 'p6.db').as_posix()}"


def hf_token() -> str:
    return (os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACEHUB_API_TOKEN") or "").strip()


def p3_base_url() -> str:
    return (os.getenv("P3_BASE_URL") or "http://127.0.0.1:8002").rstrip("/")


def p4_base_url() -> str:
    return (os.getenv("P4_BASE_URL") or "http://127.0.0.1:8002").rstrip("/")


def p5_base_url() -> str:
    return (os.getenv("P5_BASE_URL") or "http://127.0.0.1:8002").rstrip("/")

