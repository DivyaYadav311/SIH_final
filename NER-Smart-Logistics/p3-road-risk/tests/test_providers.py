from datetime import datetime, timezone

from p3_src.providers.upstream import HttpProbabilityProvider, UnavailableProbabilityProvider


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, response):
        self.response = response

    def get(self, *args, **kwargs):
        return self.response


def test_unavailable_provider_returns_null_without_fabrication():
    result = UnavailableProbabilityProvider("P1").get_probability("road", datetime.now(timezone.utc))
    assert result.available is False
    assert result.probability is None


def test_http_provider_accepts_valid_probability():
    provider = HttpProbabilityProvider("http://p1", "P1", session=FakeSession(FakeResponse({"probability": 0.7})))
    result = provider.get_probability("road", datetime.now(timezone.utc))
    assert result.available is True
    assert result.probability == 0.7


def test_http_provider_converts_timeout_or_bad_payload_to_unavailable():
    class BrokenSession:
        def get(self, *args, **kwargs):
            raise TimeoutError("timeout")

    provider = HttpProbabilityProvider("http://p2", "P2", session=BrokenSession())
    result = provider.get_probability("road", datetime.now(timezone.utc))
    assert result.available is False
    assert result.probability is None
