import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from flood_score import compute_flood_probability


def test_low_rainfall_gives_low_probability():
    # with safe terrain (high elevation, far from river), low rainfall should score low
    assert compute_flood_probability(0, elevation_m=600, river_proximity_km=15) < 0.05
    assert compute_flood_probability(25, elevation_m=600, river_proximity_km=15) < 0.15


def test_high_rainfall_gives_high_probability():
    # with risky terrain (low elevation, close to river), high rainfall should score high
    assert compute_flood_probability(300, elevation_m=20, river_proximity_km=0.5) > 0.85


def test_output_is_bounded():
    for rainfall in [0, 10, 50, 100, 150, 250, 500]:
        for elevation in [None, 10, 500]:
            for river in [None, 0.5, 20]:
                prob = compute_flood_probability(rainfall, elevation, river)
                assert 0.0 <= prob <= 1.0


def test_monotonic_increase_with_rainfall():
    values = [compute_flood_probability(r) for r in [0, 50, 100, 150, 200, 250]]
    assert values == sorted(values)


def test_low_elevation_and_close_river_increase_risk():
    base = compute_flood_probability(100, elevation_m=None, river_proximity_km=None)
    risky = compute_flood_probability(100, elevation_m=20, river_proximity_km=0.5)
    safe = compute_flood_probability(100, elevation_m=600, river_proximity_km=15)
    assert risky > base > safe


def test_missing_terrain_defaults_to_neutral():
    # Missing data shouldn't push the score to an extreme in either direction
    prob = compute_flood_probability(100, elevation_m=None, river_proximity_km=None)
    assert 0.0 < prob < 1.0
