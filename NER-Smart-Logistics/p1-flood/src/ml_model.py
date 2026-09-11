"""Train and serve the P1 flood model.

The model consumes a canonical daily table.  Keeping the canonical schema
explicit makes the joins auditable and prevents accidental target leakage.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, f1_score, precision_score, recall_score, roc_auc_score

FEATURES = [
    "rainfall_1d_mm", "rainfall_3d_mm", "rainfall_7d_mm", "rainfall_14d_mm",
    "rainfall_30d_mm", "rainfall_anomaly_7d", "rainfall_anomaly_30d",
    "elevation_m", "river_proximity_km", "latitude", "longitude", "month",
]
_ROOT = Path(__file__).resolve().parents[2]
_UNIFIED_ARTIFACT = _ROOT / "models" / "p1_flood" / "p1_flood_model.joblib"
_LOCAL_ARTIFACT = Path(__file__).resolve().parent.parent / "models" / "p1_flood_model.joblib"
DEFAULT_ARTIFACT = _UNIFIED_ARTIFACT if _UNIFIED_ARTIFACT.exists() else _LOCAL_ARTIFACT


def _validate_table(frame: pd.DataFrame) -> pd.DataFrame:
    missing = REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError(f"Training table is missing required columns: {sorted(missing)}")
    out = frame.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce", utc=True)
    if out["date"].isna().any():
        raise ValueError("Training table contains invalid dates")
    out["flood_event"] = pd.to_numeric(out["flood_event"], errors="coerce")
    if out["flood_event"].isna().any() or ~out["flood_event"].isin([0, 1]).all():
        raise ValueError("flood_event must contain only 0/1 labels")
    if out["flood_event"].nunique() < 2:
        raise ValueError("Training data needs both flood and non-flood labels")
    for col in FEATURES:
        if col not in out:
            out[col] = np.nan
        out[col] = pd.to_numeric(out[col], errors="coerce")
    return out.sort_values("date").reset_index(drop=True)


def _split_by_time(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    dates = frame["date"].sort_values().unique()
    if len(dates) < 6:
        raise ValueError("Need at least six distinct dates for train/validation/test splits")
    validation_cutoff = dates[int(len(dates) * 0.6)]
    test_cutoff = dates[int(len(dates) * 0.8)]
    train = frame[frame["date"] < validation_cutoff]
    validation = frame[(frame["date"] >= validation_cutoff) & (frame["date"] < test_cutoff)]
    test = frame[frame["date"] >= test_cutoff]
    for name, subset in (("train", train), ("validation", validation), ("test", test)):
        if subset.empty or subset["flood_event"].nunique() < 2:
            raise ValueError(f"Time split '{name}' must contain both classes; expand the historical dataset")
    return train, validation, test


def _matrix(frame: pd.DataFrame, features: list[str] = FEATURES) -> pd.DataFrame:
    # HistGradientBoosting accepts NaNs, preserving the distinction between
    # missing evidence and a measured zero.
    return frame[features].replace([np.inf, -np.inf], np.nan)


def train_model(table: pd.DataFrame, artifact_path: Path = DEFAULT_ARTIFACT, model_version: str = "p1_flood_v1") -> dict:
    frame = _validate_table(table)
    train, validation, test = _split_by_time(frame)
    active_features = [name for name in FEATURES if train[name].nunique(dropna=True) > 1]
    if not active_features:
        raise ValueError("Training data has no varying numeric features")
    model = HistGradientBoostingClassifier(
        learning_rate=0.05, max_iter=300, max_leaf_nodes=15,
        l2_regularization=1.0, random_state=42,
    )
    model.fit(_matrix(train, active_features), train["flood_event"].astype(int))
    validation_raw = model.predict_proba(_matrix(validation, active_features))[:, 1]
    raw = model.predict_proba(_matrix(test, active_features))[:, 1]

    # Calibrate on the chronological holdout. A sigmoid is more stable than
    # isotonic calibration for this weak-label dataset and preserves useful
    # probability variation at live inference time.
    if len(validation) >= 30 and validation["flood_event"].sum() >= 10:
        calibrator = LogisticRegression(C=1.0, solver="lbfgs", random_state=42)
        calibrator.fit(validation_raw.reshape(-1, 1), validation["flood_event"])
        calibrated = calibrator.predict_proba(raw.reshape(-1, 1))[:, 1]
        calibration_type = "platt_holdout"
    else:
        calibrator = None
        calibrated = raw
        calibration_type = "uncalibrated_small_holdout"

    y = test["flood_event"].astype(int).to_numpy()
    metrics = {
        "roc_auc": round(float(roc_auc_score(y, calibrated)), 6),
        "pr_auc": round(float(average_precision_score(y, calibrated)), 6),
        "brier_score": round(float(brier_score_loss(y, calibrated)), 6),
        "recall_at_0_35": round(float(recall_score(y, calibrated >= 0.35, zero_division=0)), 6),
        "precision_at_0_35": round(float(precision_score(y, calibrated >= 0.35, zero_division=0)), 6),
        "f1_at_0_35": round(float(f1_score(y, calibrated >= 0.35, zero_division=0)), 6),
        "train_rows": int(len(train)),
        "validation_rows": int(len(validation)),
        "test_rows": int(len(test)),
        "test_start": str(test["date"].min().date()),
        "test_end": str(test["date"].max().date()),
    }
    artifact = {
        "model": model,
        "calibrator": calibrator,
        "features": FEATURES,
        "active_features": active_features,
        "threshold": 0.35,
        "calibration_type": calibration_type,
        "trained_at": date.today().isoformat(),
        "metrics": metrics,
        "model_version": model_version,
    }
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, artifact_path)
    artifact_path.with_suffix(".metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    return metrics


def load_model(path: Path = DEFAULT_ARTIFACT) -> dict | None:
    if not path.exists():
        return None
    artifact = joblib.load(path)
    if artifact.get("features") != FEATURES:
        raise ValueError("P1 model feature schema does not match the current code")
    return artifact


def predict_probability(features: dict, artifact: dict) -> float:
    row = pd.DataFrame([{name: features.get(name) for name in FEATURES}])
    active_features = artifact.get("active_features", FEATURES)
    raw = float(artifact["model"].predict_proba(_matrix(row, active_features))[:, 1][0])
    calibrator = artifact.get("calibrator")
    if calibrator is not None:
        if hasattr(calibrator, "predict_proba"):
            raw = float(calibrator.predict_proba(np.array([[raw]]))[:, 1][0])
        else:
            raw = float(calibrator.predict([raw])[0])
    return round(float(np.clip(raw, 0.0, 1.0)), 3)
