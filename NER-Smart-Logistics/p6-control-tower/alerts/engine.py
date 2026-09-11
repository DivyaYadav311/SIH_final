"""Deterministic alert severity from P3/P5 fields."""
from __future__ import annotations

from p6_src.schemas import AlertEvaluateIn


def evaluate_severity(inp: AlertEvaluateIn) -> tuple[str, str, str]:
    d = inp.disruption_probability
    acc = inp.accessibility_score
    short = inp.shortage_probability
    crit = inp.critical_shipments

    if d >= 0.85 or acc <= 25 or (crit >= 1 and d >= 0.7) or short >= 0.85:
        severity = "CRITICAL"
    elif d >= 0.60 or acc <= 40 or short >= 0.60:
        severity = "HIGH"
    elif d >= 0.35 or acc <= 60 or short >= 0.35:
        severity = "MEDIUM"
    else:
        severity = "LOW"

    if severity == "CRITICAL":
        action = "REROUTE"
    elif severity == "HIGH" and d >= 0.60:
        action = "REROUTE"
    elif severity == "HIGH":
        action = "HOLD"
    elif severity == "MEDIUM":
        action = "DISPATCH_ASSESSMENT"
    else:
        action = "MONITOR"

    title = {
        "CRITICAL": "Critical road disruption",
        "HIGH": "High road disruption risk",
        "MEDIUM": "Elevated accessibility risk",
        "LOW": "Monitor road conditions",
    }[severity]
    return severity, action, title
