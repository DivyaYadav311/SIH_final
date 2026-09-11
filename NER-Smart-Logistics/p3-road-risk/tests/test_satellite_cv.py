import numpy as np

from p3_src.satellite_cv.change_detection import corridor_change
from p3_src.satellite_cv.labeling import assess_physical_road_status
from p3_src.satellite_cv.road_mask import road_mask_from_geometry
from p3_src.satellite_cv.visualization import save_comparison


def test_missing_pair_is_uncertain():
    result = assess_physical_road_status(0.9, True, False, 5, 2)
    assert result["physical_road_status"] == "UNCERTAIN"
    assert result["reason"] == "missing_before_after_pair"


def test_change_decision_is_tri_state():
    assert assess_physical_road_status(0.1, True, True, 5, 2)["physical_road_status"] == "OPEN"
    assert assess_physical_road_status(0.8, True, True, 5, 2)["physical_road_status"] == "DISRUPTED"
    assert assess_physical_road_status(0.4, True, True, 5, 2)["physical_road_status"] == "UNCERTAIN"


def test_cloud_and_resolution_never_force_a_label():
    assert assess_physical_road_status(0.9, True, True, 5, 2, cloud_affected=True)["physical_road_status"] == "UNCERTAIN"
    assert assess_physical_road_status(0.9, True, True, 5, 2, resolution_m=30)["physical_road_status"] == "UNCERTAIN"


def test_coordinate_corridor_fallback_and_change_fraction():
    mask, reason = road_mask_from_geometry(10, 10)
    assert mask.any() and reason == "event_coordinate_buffer_fallback"
    before = np.zeros((10, 10))
    after = before.copy()
    after[mask] = 1
    result = corridor_change(before, after, mask)
    assert result["changed_fraction"] == 1.0


def test_visual_artifacts_are_written(tmp_path):
    values = np.zeros((8, 8))
    paths = save_comparison(values, values + 1, values + 2, np.ones((8, 8), dtype=bool), tmp_path)
    assert all((tmp_path / f"{name}.png").exists() for name in ("before", "after", "road_mask", "before_road_overlay", "after_road_overlay", "change_map", "change_road_overlay"))
    assert set(paths) == {"before", "after", "road_mask", "before_overlay", "after_overlay", "change_map", "change_overlay"}
