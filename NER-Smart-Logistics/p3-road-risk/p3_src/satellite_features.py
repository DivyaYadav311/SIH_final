"""Deterministic, leakage-aware feature extraction from small satellite arrays."""

from __future__ import annotations

from typing import Any

import numpy as np


def robust_stats(values: Any, prefix: str) -> dict[str, float]:
    array = np.asarray(values, dtype=float)
    array = array[np.isfinite(array)]
    if array.size == 0:
        return {}
    return {
        f"{prefix}_mean": float(np.mean(array)), f"{prefix}_median": float(np.median(array)),
        f"{prefix}_std": float(np.std(array)), f"{prefix}_min": float(np.min(array)),
        f"{prefix}_max": float(np.max(array)), f"{prefix}_p10": float(np.percentile(array, 10)),
        f"{prefix}_p90": float(np.percentile(array, 90)),
    }


def _difference(before: float | None, current: float | None) -> float | None:
    return None if before is None or current is None else current - before


def extract_s1_features(phases: dict[str, dict[str, Any]]) -> dict[str, float]:
    output: dict[str, float] = {}
    means: dict[str, dict[str, float]] = {}
    for phase, bands in phases.items():
        for band in ("vv", "vh"):
            stats = robust_stats(bands.get(band), f"s1_{band}_{phase}") if band in bands else {}
            output.update(stats)
            if f"s1_{band}_{phase}_mean" in stats:
                means.setdefault(band, {})[phase] = stats[f"s1_{band}_{phase}_mean"]
    for band, values in means.items():
        before = values.get("before") or values.get("before_6_1") or values.get("before_14_7") or values.get("before_30_15")
        for phase in ("event", "after"):
            if phase in values:
                change = _difference(before, values[phase])
                if change is not None:
                    output[f"s1_{band}_{phase}_change"] = change
    if "vv" in means and "vh" in means:
        for phase in set(means["vv"]).intersection(means["vh"]):
            if means["vh"][phase] != 0:
                output[f"s1_vv_vh_ratio_{phase}"] = means["vv"][phase] / means["vh"][phase]
    return output


def extract_s2_features(phases: dict[str, dict[str, Any]]) -> dict[str, float]:
    output: dict[str, float] = {}
    means: dict[str, dict[str, float]] = {}
    for phase, bands in phases.items():
        for band in ("b02", "b03", "b04", "b08", "b11", "b12"):
            if band in bands:
                stats = robust_stats(bands[band], f"s2_{band}_{phase}")
                output.update(stats)
                if f"s2_{band}_{phase}_mean" in stats:
                    means.setdefault(band, {})[phase] = stats[f"s2_{band}_{phase}_mean"]
        if "b08" in bands and "b04" in bands:
            nir, red = np.asarray(bands["b08"], dtype=float), np.asarray(bands["b04"], dtype=float)
            ndvi = np.divide(nir - red, nir + red, out=np.full_like(nir, np.nan), where=(nir + red) != 0)
            output.update(robust_stats(ndvi, f"s2_ndvi_{phase}"))
        if "b03" in bands and "b08" in bands:
            green, nir = np.asarray(bands["b03"], dtype=float), np.asarray(bands["b08"], dtype=float)
            ndwi = np.divide(green - nir, green + nir, out=np.full_like(green, np.nan), where=(green + nir) != 0)
            output.update(robust_stats(ndwi, f"s2_ndwi_{phase}"))
    for index in ("ndvi", "ndwi"):
        before = output.get(f"s2_{index}_before_mean")
        current = output.get(f"s2_{index}_event_mean")
        change = _difference(before, current)
        if change is not None:
            output[f"s2_{index}_change"] = change
    return output


def predictive_features(features: dict[str, Any]) -> dict[str, Any]:
    """Remove all post-event fields from a prediction-time feature vector."""
    return {key: value for key, value in features.items() if not any(token in key for token in ("_after", "after_"))}