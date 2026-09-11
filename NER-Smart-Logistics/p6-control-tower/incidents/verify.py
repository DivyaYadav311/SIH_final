"""Image verification: EXIF GPS always; HF Inference API if token, else local CLIP."""
from __future__ import annotations

import io
import logging
import math
from typing import Any

import httpx
from PIL import Image, ExifTags

from p6_src.config import CLIP_LABELS, EXIF_MISMATCH_KM, HF_CLIP_MODEL, hf_token

log = logging.getLogger(__name__)

HF_URL = "https://api-inference.huggingface.co/models/{model}"

_clip_model = None
_clip_processor = None


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def _to_deg(value: Any) -> float | None:
    try:
        if isinstance(value, (tuple, list)) and len(value) == 3:
            d, m, s = value
            return float(d) + float(m) / 60.0 + float(s) / 3600.0
        return float(value)
    except (TypeError, ValueError):
        return None


def extract_exif_gps(image_bytes: bytes) -> tuple[float, float] | None:
    try:
        img = Image.open(io.BytesIO(image_bytes))
        exif = img.getexif()
        if not exif:
            return None
        gps_ifd = None
        gps_tag = next((k for k, v in ExifTags.TAGS.items() if v == "GPSInfo"), None)
        if gps_tag is not None:
            gps_ifd = exif.get_ifd(gps_tag) if hasattr(exif, "get_ifd") else exif.get(gps_tag)
        if not gps_ifd:
            return None
        gps_labels = {ExifTags.GPSTAGS.get(k, k): v for k, v in dict(gps_ifd).items()}
        lat = _to_deg(gps_labels.get("GPSLatitude"))
        lon = _to_deg(gps_labels.get("GPSLongitude"))
        if lat is None or lon is None:
            return None
        if gps_labels.get("GPSLatitudeRef") in ("S", b"S"):
            lat = -lat
        if gps_labels.get("GPSLongitudeRef") in ("W", b"W"):
            lon = -lon
        return lat, lon
    except Exception as exc:
        log.info("EXIF GPS not available: %s", exc)
        return None


def download_image(url: str, timeout: float = 20.0) -> bytes:
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        r = client.get(url)
        r.raise_for_status()
        return r.content


def _parse_clip_scores(payload: Any) -> tuple[str, float]:
    scores: dict[str, float] = {}
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                label = str(item.get("label") or item.get("token") or "").upper().replace(" ", "_")
                score = float(item.get("score") or item.get("probability") or 0.0)
                scores[label] = score
    elif isinstance(payload, dict):
        if "error" in payload:
            raise RuntimeError(str(payload["error"]))
        for item in payload.get("labels", []) if isinstance(payload.get("scores"), list) else []:
            pass
        for key, val in payload.items():
            if isinstance(val, (int, float)) and str(key).upper() in CLIP_LABELS:
                scores[str(key).upper()] = float(val)
    if not scores:
        raise RuntimeError("CLIP response had no class scores")
    best = max(scores, key=scores.get)
    mapped = best if best in CLIP_LABELS else next((l for l in CLIP_LABELS if l in best or best in l), "LANDSLIDE")
    return mapped, max(0.0, min(1.0, scores[best]))


def classify_huggingface(image_bytes: bytes) -> tuple[str, float, str]:
    token = hf_token()
    if not token:
        raise RuntimeError("HF_TOKEN not set")
    url = HF_URL.format(model=HF_CLIP_MODEL)
    headers = {"Authorization": f"Bearer {token}"}
    params = {"candidate_labels": ",".join(CLIP_LABELS)}
    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        r = client.post(url, headers=headers, content=image_bytes, params=params)
        if r.status_code == 503:
            r = client.post(url, headers=headers, content=image_bytes, params=params)
        r.raise_for_status()
        detected, confidence = _parse_clip_scores(r.json())
    return detected, confidence, "huggingface_api"


def _load_local_clip() -> None:
    global _clip_model, _clip_processor
    if _clip_model is not None:
        return
    from transformers import CLIPModel, CLIPProcessor

    _clip_processor = CLIPProcessor.from_pretrained(HF_CLIP_MODEL)
    _clip_model = CLIPModel.from_pretrained(HF_CLIP_MODEL)
    _clip_model.eval()


def classify_local_clip(image_bytes: bytes) -> tuple[str, float, str]:
    import torch

    _load_local_clip()
    assert _clip_model is not None and _clip_processor is not None
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    prompts = [f"a photo of a {label.lower().replace('_', ' ')} on a road in Northeast India" for label in CLIP_LABELS]
    inputs = _clip_processor(text=prompts, images=image, return_tensors="pt", padding=True)
    with torch.no_grad():
        out = _clip_model(**inputs)
        probs = out.logits_per_image.softmax(dim=1)[0]
    idx = int(probs.argmax().item())
    return CLIP_LABELS[idx], float(probs[idx].item()), "local_clip"


def classify_image(image_bytes: bytes) -> tuple[str, float, str]:
    if hf_token():
        try:
            return classify_huggingface(image_bytes)
        except Exception as exc:
            log.warning("Hugging Face CLIP failed, trying local CLIP: %s", exc)
    try:
        return classify_local_clip(image_bytes)
    except Exception as exc:
        log.warning("Local CLIP unavailable: %s", exc)
        raise RuntimeError(
            "Image classification unavailable: set HF_TOKEN or install transformers+torch"
        ) from exc


def verify_image(image_url: str, reported_lat: float, reported_lon: float) -> dict[str, Any]:
    image_bytes = download_image(image_url)
    gps = extract_exif_gps(image_bytes)
    mismatch = False
    distance = None
    if gps is not None:
        distance = round(haversine_km(reported_lat, reported_lon, gps[0], gps[1]), 3)
        mismatch = distance > EXIF_MISMATCH_KM
    detected, confidence, backend = classify_image(image_bytes)
    return {
        "detected_type": detected,
        "confidence": round(confidence, 4),
        "verification_backend": backend,
        "exif_gps_mismatch": mismatch,
        "exif_distance_km": distance,
    }
