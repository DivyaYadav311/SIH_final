"""String IDs: INC_*, ALERT_*, SCENARIO_*."""
from __future__ import annotations

from datetime import datetime, timezone


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def next_id(session, model, column: str, prefix: str, start: int = 1001) -> str:
    rows = session.query(getattr(model, column)).all()
    max_n = start - 1
    for (value,) in rows:
        if not value:
            continue
        parts = str(value).rsplit("_", 1)
        if len(parts) == 2 and parts[1].isdigit():
            max_n = max(max_n, int(parts[1]))
    return f"{prefix}_{max_n + 1}"
