import os

import httpx


class P4RouteClient:

    def __init__(self):
        self.base_url = os.getenv(
            "P4_BASE_URL",
            "http://127.0.0.1:8001"
        ).rstrip("/")

        self.timeout = float(
            os.getenv(
                "P4_TIMEOUT_SECONDS",
                "180"
            )
        )

    def optimize_route(
        self,
        origin: str,
        destination: str,
        cargo_type: str,
        priority: str
    ) -> dict:

        payload = {
            "origin": origin,
            "destination": destination,
            "cargo_type": cargo_type.lower(),
            "priority": priority.lower(),
            "transport_mode": "road"
        }

        url = (
            f"{self.base_url}"
            "/api/v1/routes/optimize"
        )

        try:
            response = httpx.post(
                url,
                json=payload,
                timeout=self.timeout
            )

        except httpx.RequestError as exc:
            raise RuntimeError(
                f"P4 is unreachable at "
                f"{self.base_url}: {exc}"
            ) from exc

        if response.status_code >= 400:

            try:
                detail = response.json()
            except Exception:
                detail = response.text

            raise RuntimeError(
                f"P4 route request failed "
                f"({response.status_code}): {detail}"
            )

        try:
            result = response.json()
        except Exception as exc:
            raise RuntimeError(
                "P4 returned invalid JSON"
            ) from exc

        required_fields = [
            "route_id",
            "estimated_travel_time_minutes",
            "route_risk"
        ]

        missing = [
            field
            for field in required_fields
            if field not in result
        ]

        if missing:
            raise RuntimeError(
                f"P4 response is missing fields: {missing}"
            )

        return result
