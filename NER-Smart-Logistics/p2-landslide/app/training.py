"""Training utilities for the landslide classifier."""

import csv
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import GroupShuffleSplit, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier

from app.scoring import FEATURE_ORDER

LABEL_COLUMN = "landslide_occurred"
MINIMUM_ROWS = 20


def _read_dataset(dataset_path: Path) -> tuple[list[list[float]], list[int]]:
    with dataset_path.open("r", newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        if not reader.fieldnames:
            raise ValueError("The training CSV must include a header row.")

        missing = set(FEATURE_ORDER + [LABEL_COLUMN]) - set(reader.fieldnames)
        if missing:
            raise ValueError(f"Training CSV is missing required columns: {sorted(missing)}")

        features: list[list[float]] = []
        labels: list[int] = []
        for row_number, row in enumerate(reader, start=2):
            try:
                feature_row = [float(row[name]) for name in FEATURE_ORDER]
                label = int(row[LABEL_COLUMN])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid numeric value on CSV row {row_number}.") from exc
            if not all(math.isfinite(value) for value in feature_row):
                raise ValueError(f"Feature values must be finite on CSV row {row_number}.")
            if label not in (0, 1):
                raise ValueError(f"{LABEL_COLUMN} must be 0 or 1 on CSV row {row_number}.")
            features.append(feature_row)
            labels.append(label)

    if len(features) < MINIMUM_ROWS:
        raise ValueError(f"At least {MINIMUM_ROWS} labelled rows are required; received {len(features)}.")
    if len(set(labels)) != 2:
        raise ValueError("Training data must include both non-landslide (0) and landslide (1) rows.")
    return features, labels


def train_model(
    dataset_path: str | Path,
    output_path: str | Path,
    *,
    model_version: str = "landslide_logistic_regression_v1",
    training_data_kind: str = "verified_observations",
) -> dict[str, Any]:
    """Train and save a balanced logistic-regression classifier."""
    dataset = Path(dataset_path)
    output = Path(output_path)
    features, labels = _read_dataset(dataset)
    class_counts = Counter(labels)
    if min(class_counts.values()) < 5:
        raise ValueError("Each class needs at least five observations for a stratified holdout.")

    if training_data_kind == "gsi_inventory_with_pseudo_absences":
        # Keep nearby locations together so validation measures transfer to
        # unseen geographic cells rather than memorisation of local clusters.
        groups = [f"{int(row[0] * 2)}:{int(row[1] * 2)}" for row in features]
        splitter = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
        train_indices, test_indices = next(splitter.split(features, labels, groups))
        train_features = [features[index] for index in train_indices]
        test_features = [features[index] for index in test_indices]
        train_labels = [labels[index] for index in train_indices]
        test_labels = [labels[index] for index in test_indices]
        validation_method = "spatial_grid_holdout_0.5_degree"
    else:
        train_features, test_features, train_labels, test_labels = train_test_split(
            features, labels, test_size=0.2, random_state=42, stratify=labels
        )
        validation_method = "stratified_random_holdout"
    if training_data_kind == "gsi_inventory_with_pseudo_absences":
        # Landslide inventories form non-linear geographic clusters. A forest
        # can learn these spatial boundaries without extrapolating a straight
        # latitude/longitude trend across the entire country.
        classifier = RandomForestClassifier(
            n_estimators=250,
            max_depth=18,
            min_samples_leaf=4,
            class_weight="balanced_subsample",
            # Keep training compatible with restricted Windows environments.
            n_jobs=1,
            random_state=42,
        )
        model_type = "random_forest_spatial_susceptibility"
    else:
        classifier = Pipeline([
            ("scaler", StandardScaler()),
            ("classifier", LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42)),
        ])
        model_type = "standard_scaled_logistic_regression"
    classifier.fit(train_features, train_labels)
    probabilities = classifier.predict_proba(test_features)[:, 1]
    metrics = {
        "training_rows": len(features),
        "positive_rows": class_counts[1],
        "negative_rows": class_counts[0],
        "validation_rows": len(test_labels),
        "validation_method": validation_method,
        "roc_auc": round(float(roc_auc_score(test_labels, probabilities)), 4),
        "average_precision": round(float(average_precision_score(test_labels, probabilities)), 4),
    }
    artifact = {
        "artifact_version": 1,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "model_type": model_type,
        "model_version": model_version,
        "training_data_kind": training_data_kind,
        "model": classifier,
        "feature_order": FEATURE_ORDER,
        "label_column": LABEL_COLUMN,
        "metrics": metrics,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, output)
    return metrics


def write_metrics(metrics: dict[str, Any]) -> str:
    return json.dumps(metrics, indent=2, sort_keys=True)
