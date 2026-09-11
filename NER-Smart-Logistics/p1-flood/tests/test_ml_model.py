import numpy as np
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ml_model import FEATURES, predict_probability, train_model


def test_model_uses_future_holdout_and_predicts_bounded_probability(tmp_path):
    dates = pd.date_range("2020-01-01", periods=120, freq="D", tz="UTC")
    rainfall = np.arange(120, dtype=float) % 12
    labels = (rainfall >= 6).astype(int)
    frame = pd.DataFrame({
        "date": dates,
        "segment_id": ["S1"] * 120,
        "flood_event": labels,
        "rainfall_1d_mm": rainfall,
        "rainfall_3d_mm": rainfall * 2,
        "rainfall_7d_mm": rainfall * 4,
        "elevation_m": 100.0,
        "river_proximity_km": 1.0,
        "latitude": 26.0,
        "longitude": 91.0,
        "month": dates.month,
    })
    path = tmp_path / "model.joblib"
    metrics = train_model(frame, path)
    assert metrics["train_rows"] > 0
    assert metrics["validation_rows"] > 0
    assert metrics["test_rows"] > 0

    import joblib
    artifact = joblib.load(path)
    probability = predict_probability(
        {name: frame.iloc[-1].get(name) for name in FEATURES}, artifact
    )
    assert 0.0 <= probability <= 1.0
