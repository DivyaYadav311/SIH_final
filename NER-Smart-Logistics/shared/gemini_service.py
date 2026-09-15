"""
Gemini AI Intelligence Service for Pravah Platform
===================================================
Connects to Google Generative AI API using configured environment settings:
- GEMINI_API_KEY
- GEMINI_MODEL (default: gemini-3.7-flash, with automatic fallback)
- GEMINI_TIMEOUT_SECONDS (default: 15)
- GEMINI_TEMPERATURE (default: 0.2)
Provides disaster routing advisories, hazard explanations, and control tower recommendations.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional
import httpx

log = logging.getLogger("pravah-gemini")

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


def get_gemini_config() -> dict[str, Any]:
    return {
        "api_key": os.getenv("GEMINI_API_KEY", "").strip(),
        "model": os.getenv("GEMINI_MODEL", "gemini-3.7-flash").strip(),
        "timeout": float(os.getenv("GEMINI_TIMEOUT_SECONDS", "15")),
        "temperature": float(os.getenv("GEMINI_TEMPERATURE", "0.2")),
    }


def call_gemini(
    prompt: str,
    system_instruction: Optional[str] = None,
    preferred_model: Optional[str] = None,
) -> Optional[str]:
    """Call Google Generative Language API with resilient model fallback."""
    cfg = get_gemini_config()
    api_key = cfg["api_key"]
    if not api_key:
        log.info("GEMINI_API_KEY not configured; using deterministic advisory fallback.")
        return None

    primary_model = preferred_model or cfg["model"]
    # Fallback chain in case of temporary 503 or 429 capacity limits
    candidate_models = ["gemini-flash-lite-latest", primary_model, "gemini-flash-latest", "gemini-3.7-flash"]

    payload: dict[str, Any] = {
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ],
        "generationConfig": {
            "temperature": cfg["temperature"],
            "maxOutputTokens": 800,
        },
    }

    if system_instruction:
        payload["systemInstruction"] = {
            "parts": [{"text": system_instruction}]
        }

    timeout_sec = cfg["timeout"]

    for model in candidate_models:
        url = f"{GEMINI_API_BASE}/{model}:generateContent?key={api_key}"
        try:
            with httpx.Client(timeout=timeout_sec, follow_redirects=True) as client:
                resp = client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts and "text" in parts[0]:
                            return parts[0]["text"].strip()
                elif resp.status_code in (503, 429, 404):
                    log.warning("Gemini model %s returned HTTP %s, trying fallback...", model, resp.status_code)
                    continue
                else:
                    log.warning("Gemini API error (%s): %s", resp.status_code, resp.text[:200])
                    break
        except Exception as exc:
            log.warning("Gemini request failed for model %s: %s", model, exc)
            continue

    return None


def generate_route_advisory(route_context: dict[str, Any]) -> dict[str, Any]:
    """
    Generate an AI Disaster Route Advisory for the given origin, destination,
    and hazard parameters.
    """
    origin = route_context.get("origin", "Guwahati")
    dest = route_context.get("destination", "Shillong")
    distance_km = route_context.get("distance_km", 98.0)
    duration_min = route_context.get("duration_minutes", 150.0)
    risk_level = route_context.get("risk_level", "MODERATE")
    flood_prob = route_context.get("flood_probability", 0.25)
    landslide_prob = route_context.get("landslide_probability", 0.35)
    road_disruption = route_context.get("disruption_probability", 0.30)
    cargo_type = route_context.get("cargo_type", "General Goods")
    imd_alerts = route_context.get("imd_alerts_count", 0)

    system_prompt = (
        "You are PRAVAH's AI Disaster Logistics Advisory Engine for Northeast India (SIH26002). "
        "Provide professional, concise, actionable intelligence for convoy dispatchers and emergency logistics. "
        "Structure your response with clear sections: 1. OVERALL ADVISORY, 2. CORRIDOR HAZARD PROFILE, 3. RECOMMENDED PRECAUTIONS & PROTOCOLS."
    )

    user_prompt = f"""
Analyze the following transport corridor in Northeast India:
- Route: {origin} to {dest}
- Distance: {distance_km:.1f} km (Estimated Time: {duration_min:.0f} mins)
- Cargo: {cargo_type}
- Assessed Risk Level: {risk_level}
- Flood Hazard Probability: {flood_prob:.2f}
- Landslide Hazard Probability: {landslide_prob:.2f}
- Road Disruption Probability: {road_disruption:.2f}
- Active IMD Weather Alerts on Corridor: {imd_alerts}

Generate a concise (150-200 words) tactical intelligence advisory for route dispatchers.
Highlight specific weather/terrain considerations relevant to this Northeast Indian geography.
"""

    gemini_text = call_gemini(user_prompt, system_instruction=system_prompt)

    if gemini_text:
        return {
            "source": "gemini-ai",
            "model": get_gemini_config()["model"],
            "advisory_text": gemini_text,
            "status": "success",
        }

    # Deterministic fallback when API key is missing or offline
    fallback_text = (
        f"**Corridor Operational Advisory ({origin} -> {dest})**\n\n"
        f"• **Risk Evaluation**: Assessed risk level is **{risk_level}** across {distance_km:.1f} km.\n"
        f"• **Hazard Dynamics**: Flood risk is rated at {int(flood_prob*100)}%, landslide susceptibility at {int(landslide_prob*100)}%, and disruption likelihood at {int(road_disruption*100)}%.\n"
        f"• **Convoy Dispatch Protocol**: For {cargo_type}, maintain telemetry tracking, verify IMD rainfall warnings before entering ghat sections, and keep satellite communications active at high-elevation chokepoints."
    )
    return {
        "source": "deterministic-fallback",
        "model": "rule-based-v3",
        "advisory_text": fallback_text,
        "status": "fallback",
    }
