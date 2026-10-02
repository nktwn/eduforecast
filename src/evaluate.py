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
    results: list[tuple[int, float]] = []
    for week_idx, (X, y) in enumerate(zip(X_by_week, y_by_week), start=1):
        if len(np.unique(y)) < 2:
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
    out_dir = Path(output_dir) if output_dir else METRICS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame([metrics_dict])
    df.insert(0, "model", model_name)

    out_path = out_dir / f"{model_name}_metrics.csv"
    df.to_csv(out_path, index=False)
    print(f"Metrics saved → {out_path}")
    return out_path


def compare_models(metrics_dir: Path | None = None) -> pd.DataFrame:
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
