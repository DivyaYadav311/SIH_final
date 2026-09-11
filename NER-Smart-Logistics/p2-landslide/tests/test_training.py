import csv

import pytest

from app.scoring import FEATURE_ORDER
from app.training import train_model


def _write_dataset(path, rows):
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=FEATURE_ORDER + ["landslide_occurred"])
        writer.writeheader()
        writer.writerows(rows)


def test_training_creates_compatible_model(tmp_path):
    rows = []
    for index in range(24):
        row = {feature: float(index) for feature in FEATURE_ORDER}
        row["landslide_occurred"] = index % 2
        rows.append(row)
    dataset = tmp_path / "observations.csv"
    artifact = tmp_path / "model.pkl"
    _write_dataset(dataset, rows)
    metrics = train_model(dataset, artifact)
    assert artifact.exists()
    assert metrics["training_rows"] == 24
    assert 0.0 <= metrics["roc_auc"] <= 1.0


def test_training_rejects_unlabelled_data(tmp_path):
    dataset = tmp_path / "observations.csv"
    dataset.write_text("rainfall_1h_mm\\n1\\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing required columns"):
        train_model(dataset, tmp_path / "model.pkl")
