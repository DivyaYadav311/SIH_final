from __future__ import annotations

from typing import Any

import numpy as np


def image_change(before: np.ndarray, after: np.ndarray) -> dict[str, Any]:
    before = np.asarray(before, dtype=float)
    after = np.asarray(after, dtype=float)
    if before.shape != after.shape:
        raise ValueError("before and after arrays must have identical shapes")
    scale = np.nanpercentile(np.abs(before), 90)
    scale = max(float(scale), 1e-6)
    difference = np.abs(after - before) / scale
    difference[~np.isfinite(difference)] = np.nan
    return {"change_map": difference, "mean_change": float(np.nanmean(difference))}


def corridor_change(before: np.ndarray, after: np.ndarray, mask: np.ndarray, threshold: float = 0.35) -> dict[str, Any]:
    result = image_change(before, after)
    values = result["change_map"][mask]
    values = values[np.isfinite(values)]
    if values.size == 0:
        return {**result, "changed_fraction": None, "background_mean": None}
    changed = values >= threshold
    background_values = result["change_map"][~mask]
    background_values = background_values[np.isfinite(background_values)]
    corridor_mean = float(np.mean(values))
    background_mean = float(np.mean(background_values)) if background_values.size else None
    concentration = None if background_mean is None else corridor_mean / max(background_mean, 1e-6)
    return {**result, "changed_fraction": float(np.mean(changed)), "corridor_mean": corridor_mean, "background_mean": background_mean, "road_change_concentration": concentration}