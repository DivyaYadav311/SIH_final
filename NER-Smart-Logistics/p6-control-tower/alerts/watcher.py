"""Background watcher for newly published official IMD CAP warnings."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging

from alerts.imd import fetch_imd_cap_alerts
from p6_src.config import IMD_POLL_SECONDS
from p6_src.hub import AlertHub

log = logging.getLogger(__name__)


def _alert_key(alert: dict) -> str:
    """Create a stable key from official CAP fields when no identifier is present."""
    source = json.dumps(
        {
            "identifier": alert.get("identifier"),
            "headline": alert.get("headline"),
            "event": alert.get("event"),
            "area": alert.get("area"),
            "expires": alert.get("expires"),
        },
        sort_keys=True,
    )
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


class IMDAlertWatcher:
    """Poll IMD WIS2 and broadcast only CAP warnings not seen in this run."""

    def __init__(self, hub: AlertHub) -> None:
        self._hub = hub
        self._seen: set[str] = set()
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run(), name="p6-imd-cap-watcher")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def _run(self) -> None:
        first_poll = True
        while True:
            try:
                alerts = await asyncio.to_thread(fetch_imd_cap_alerts)
                keys = {_alert_key(alert) for alert in alerts}
                if first_poll:
                    # Existing official warnings remain available via REST; avoid
                    # treating them as newly-arrived notifications on startup.
                    self._seen = keys
                    first_poll = False
                else:
                    for alert in alerts:
                        key = _alert_key(alert)
                        if key not in self._seen:
                            await self._hub.broadcast({"type": "imd_cap_alert", "alert": alert})
                    self._seen = keys
            except Exception as exc:
                log.warning("IMD CAP watcher poll failed: %s", exc)
            await asyncio.sleep(IMD_POLL_SECONDS)
