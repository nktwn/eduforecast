"""Metrics computation, persistence, and model comparison utilities."""

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    auc,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)

from .config import METRICS_DIR


def compute_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_prob: np.ndarray,
) -> dict[str, float]:
    """Compute standard binary-classification metrics.

    Parameters
    ----------
    y_true:
        Ground-truth binary labels.
    y_pred:
        Hard (thresholded) predictions.
    y_prob:
        Predicted probabilities for the positive class.

    Returns
    -------
    Dict with keys: ``accuracy``, ``precision``, ``recall``, ``f1``, ``auc_roc``.
    """
    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1": f1_score(y_true, y_pred, zero_division=0),
        "auc_roc": roc_auc_score(y_true, y_prob),
    }


def compute_temporal_auc(
    model: Any,
    X_by_week: list[np.ndarray],
    y_by_week: list[np.ndarray],
) -> list[tuple[int, float]]:
    """Evaluate model AUC-ROC at each week of the semester.

    Parameters
    ----------
    model:
        Fitted model with a ``predict_proba`` method.
    X_by_week:
        List of feature arrays indexed by week (index 0 → week 1).
    y_by_week:
        List of label arrays indexed by week.

    Returns
    -------
    List of ``(week, auc)`` tuples for weeks 1–N.
    """
    results: list[tuple[int, float]] = []
    for week_idx, (X, y) in enumerate(zip(X_by_week, y_by_week), start=1):
        if len(np.unique(y)) < 2:
            # Cannot compute AUC with a single class present
            continue
        if hasattr(model, "predict_proba"):
            probs = model.predict_proba(X)[:, 1]
        else:
            probs = model.predict(X)
        week_auc = roc_auc_score(y, probs)
        results.append((week_idx, week_auc))
    return results


def save_metrics(
    metrics_dict: dict[str, float],
    model_name: str,
    output_dir: Path | None = None,
) -> Path:
    """Persist a metrics dict as a CSV file.

    Parameters
    ----------
    metrics_dict:
        Output of :func:`compute_metrics`.
    model_name:
        Used as the filename stem (e.g. ``"random_forest"``).
    output_dir:
        Directory to write into. Defaults to ``config.METRICS_DIR``.

    Returns
    -------
    Path to the written CSV file.
    """
    out_dir = Path(output_dir) if output_dir else METRICS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame([metrics_dict])
    df.insert(0, "model", model_name)

    out_path = out_dir / f"{model_name}_metrics.csv"
    df.to_csv(out_path, index=False)
    print(f"Metrics saved → {out_path}")
    return out_path


def compare_models(metrics_dir: Path | None = None) -> pd.DataFrame:
    """Load all ``*_metrics.csv`` files and return a comparison DataFrame.

    Parameters
    ----------
    metrics_dir:
        Directory that contains the per-model CSV files.
        Defaults to ``config.METRICS_DIR``.

    Returns
    -------
    DataFrame with one row per model, sorted descending by AUC-ROC.
    """
    search_dir = Path(metrics_dir) if metrics_dir else METRICS_DIR
    csv_files = sorted(search_dir.glob("*_metrics.csv"))

    if not csv_files:
        print(f"No metric files found in {search_dir}")
        return pd.DataFrame()

    frames = [pd.read_csv(f) for f in csv_files]
    comparison = pd.concat(frames, ignore_index=True).sort_values(
        "auc_roc", ascending=False
    )

    print("\nModel comparison (sorted by AUC-ROC):")
    print(comparison.to_string(index=False, float_format="{:.4f}".format))
    return comparison
