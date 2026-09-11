from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


def _image(array: np.ndarray) -> Image.Image:
    values = np.asarray(array, dtype=float)
    finite = values[np.isfinite(values)]
    low, high = (float(np.percentile(finite, 2)), float(np.percentile(finite, 98))) if finite.size else (0.0, 1.0)
    scaled = np.clip((values - low) / max(high - low, 1e-6), 0, 1) * 255
    return Image.fromarray(np.nan_to_num(scaled).astype("uint8")).convert("RGB")


def save_comparison(before: np.ndarray, after: np.ndarray, change: np.ndarray, mask: np.ndarray, output_dir: str | Path) -> dict[str, str]:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    before_image, after_image, change_image = _image(before), _image(after), _image(change)
    before_overlay = before_image.copy()
    after_overlay = after_image.copy()
    change_overlay = change_image.copy()
    draw_before = ImageDraw.Draw(before_overlay)
    draw_after = ImageDraw.Draw(after_overlay)
    draw_change = ImageDraw.Draw(change_overlay)
    height, width = mask.shape
    columns = np.where(mask.any(axis=0))[0]
    if columns.size:
        bounds = (int(columns.min()), 0, int(columns.max()), height - 1)
        draw_before.rectangle(bounds, outline="red", width=2)
        draw_after.rectangle(bounds, outline="red", width=2)
        draw_change.rectangle(bounds, outline="red", width=2)
    mask_image = Image.fromarray((mask.astype("uint8") * 255)).convert("L")
    paths = {"before": directory / "before.png", "after": directory / "after.png", "road_mask": directory / "road_mask.png", "before_overlay": directory / "before_road_overlay.png", "after_overlay": directory / "after_road_overlay.png", "change_map": directory / "change_map.png", "change_overlay": directory / "change_road_overlay.png"}
    before_image.save(paths["before"])
    after_image.save(paths["after"])
    change_image.save(paths["change_map"])
    mask_image.save(paths["road_mask"])
    before_overlay.save(paths["before_overlay"])
    after_overlay.save(paths["after_overlay"])
    change_overlay.save(paths["change_overlay"])
    return {key: str(value) for key, value in paths.items()}