from __future__ import annotations

from typing import Any

import numpy as np
from PIL import Image, ImageDraw


def coordinate_buffer_mask(height: int, width: int, corridor_fraction: float = 0.18) -> np.ndarray:
    """Use a narrow central corridor when no defensible OSM geometry is available."""
    mask = np.zeros((height, width), dtype=bool)
    half = max(1, int(width * corridor_fraction / 2))
    center = width // 2
    mask[:, max(0, center - half):min(width, center + half + 1)] = True
    return mask


def road_mask_from_geometry(height: int, width: int, geometry: Any | None = None) -> tuple[np.ndarray, str]:
    """Return an explicit fallback unless a rasterized geometry implementation is supplied."""
    if not geometry:
        return coordinate_buffer_mask(height, width), "event_coordinate_buffer_fallback"
    bbox = geometry["bbox"]
    points = geometry["coordinates"]
    image = Image.new("1", (width, height), 0)
    draw = ImageDraw.Draw(image)
    west, south, east, north = bbox
    pixels = []
    for longitude, latitude in points:
        x = round((longitude - west) / max(east - west, 1e-9) * (width - 1))
        y = round((north - latitude) / max(north - south, 1e-9) * (height - 1))
        pixels.append((x, y))
    if len(pixels) < 2:
        return coordinate_buffer_mask(height, width), "coordinate_buffer_invalid_geometry"
    draw.line(pixels, fill=1, width=max(1, round(width * 0.05)))
    return np.asarray(image, dtype=bool), "osm_overpass"