from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import requests


@dataclass(frozen=True)
class ProbabilityResult:
    location_id: str
    timestamp: datetime
    probability: float | None
    available: bool
    error: str | None = None


class ProbabilityProvider:
    def get_probability(self, location_id: str, timestamp: datetime) -> ProbabilityResult:
        raise NotImplementedError


class UnavailableProbabilityProvider(ProbabilityProvider):
    def __init__(self, provider_name: str):
        self.provider_name = provider_name

    def get_probability(self, location_id: str, timestamp: datetime) -> ProbabilityResult:
        return ProbabilityResult(
            location_id=location_id,
            timestamp=timestamp,
            probability=None,
            available=False,
            error=f"{self.provider_name} provider unavailable",
        )


class HttpProbabilityProvider(ProbabilityProvider):
    def __init__(self, endpoint: str, provider_name: str, timeout_seconds: float = 2.0, session: Any = None):
        self.endpoint = endpoint.rstrip("/")
        self.provider_name = provider_name
        self.timeout_seconds = timeout_seconds
        self.session = session or requests.Session()

    def get_probability(self, location_id: str, timestamp: datetime) -> ProbabilityResult:
        try:
            response = self.session.get(
                self.endpoint,
                params={"location_id": location_id, "timestamp": timestamp.isoformat()},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            probability = payload.get("probability")
            if probability is None or not 0.0 <= float(probability) <= 1.0:
                raise ValueError("provider returned probability outside [0, 1]")
            return ProbabilityResult(location_id, timestamp, float(probability), True)
        except (requests.RequestException, TimeoutError, ValueError, TypeError, KeyError) as exc:
            return ProbabilityResult(location_id, timestamp, None, False, f"{self.provider_name}: {exc}")


class FloodProbabilityProvider(ProbabilityProvider):
    pass


class LandslideProbabilityProvider(ProbabilityProvider):
    pass
