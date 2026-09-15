from __future__ import annotations

from incidents.verify import haversine_km, verify_image


def test_haversine_known_distance():
    km = haversine_km(27.58, 91.87, 26.1445, 91.7362)
    assert km > 100


def test_exif_mismatch_flag(monkeypatch):
    monkeypatch.setattr("incidents.verify.download_image", lambda url: b"fake-bytes")
    monkeypatch.setattr("incidents.verify.extract_exif_gps", lambda data: (26.1445, 91.7362))
    monkeypatch.setattr(
        "incidents.verify.classify_image",
        lambda data: ("LANDSLIDE", 0.94, "huggingface_api"),
    )
    result = verify_image("https://example.invalid/x.jpg", 27.58, 91.87)
    assert result["detected_type"] == "LANDSLIDE"
    assert result["confidence"] == 0.94
    assert result["verification_backend"] == "huggingface_api"
    assert result["exif_gps_mismatch"] is True
    assert result["exif_distance_km"] > 5


def test_exif_match_nearby(monkeypatch):
    monkeypatch.setattr("incidents.verify.download_image", lambda url: b"fake-bytes")
    monkeypatch.setattr("incidents.verify.extract_exif_gps", lambda data: (27.5801, 91.8701))
    monkeypatch.setattr(
        "incidents.verify.classify_image",
        lambda data: ("FLOOD", 0.81, "local_clip"),
    )
    result = verify_image("https://example.invalid/x.jpg", 27.58, 91.87)
    assert result["exif_gps_mismatch"] is False
    assert result["verification_backend"] == "local_clip"


def test_create_runs_verification(client, monkeypatch):
    monkeypatch.setattr(
        "incidents.router.verify_image",
        lambda url, lat, lon: {
            "detected_type": "LANDSLIDE",
            "confidence": 0.94,
            "verification_backend": "huggingface_api",
            "exif_gps_mismatch": False,
            "exif_distance_km": 0.2,
        },
    )
    r = client.post(
        "/api/v1/incidents",
        json={
            "incident_id": "INC_1001",
            "reported_by": "DRIVER_123",
            "latitude": 27.58,
            "longitude": 91.87,
            "incident_type": "LANDSLIDE",
            "image_url": "https://example.invalid/slide.jpg",
        },
    )
    body = r.json()
    assert body["status"] == "UNDER_VERIFICATION"
    assert body["detected_type"] == "LANDSLIDE"
    assert body["confidence"] == 0.94
    assert body["verification_backend"] == "huggingface_api"


def test_clear_image_is_rejected_when_verified(client, monkeypatch):
    monkeypatch.setattr(
        "incidents.router.verify_image",
        lambda url, lat, lon: {
            "detected_type": "CLEAR",
            "confidence": 0.97,
            "verification_backend": "huggingface_api",
            "exif_gps_mismatch": False,
            "exif_distance_km": 0.1,
        },
    )
    created = client.post(
        "/api/v1/incidents",
        json={
            "reported_by": "DRIVER_123",
            "latitude": 27.58,
            "longitude": 91.87,
            "incident_type": "LANDSLIDE",
            "image_url": "https://example.invalid/flower.jpg",
        },
    )
    incident_id = created.json()["incident_id"]
    verified = client.post(f"/api/v1/incidents/{incident_id}/verify")
    assert verified.status_code == 200
    assert verified.json()["status"] == "REJECTED"
