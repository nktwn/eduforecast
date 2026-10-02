from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
from sklearn.metrics import ConfusionMatrixDisplay, roc_curve

from .config import FIGURES_DIR

plt.style.use("seaborn-v0_8-whitegrid")
_FIG_SIZE_DEFAULT = (10, 6)
_FIG_SIZE_WIDE = (12, 8)
_DPI = 300


def _save(fig: plt.Figure, save_path: Path | str) -> None:
    base = Path(save_path).with_suffix("")
    for ext in (".png", ".pdf"):
        out = base.with_suffix(ext)
        out.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out, dpi=_DPI, bbox_inches="tight")
        print(f"Saved → {out}")
    plt.close(fig)


def plot_temporal_auc(
    results_dict: dict[str, list[tuple[int, float]]],
    save_path: Optional[Path | str] = None,
) -> plt.Figure:
    fig, ax = plt.subplots(figsize=_FIG_SIZE_WIDE)
    for model_name, weekly_results in results_dict.items():
        if not weekly_results:
            continue
        weeks, aucs = zip(*weekly_results)
        ax.plot(weeks, aucs, marker="o", markersize=4, linewidth=2, label=model_name)

    ax.set_xlabel("Week", fontsize=13)
    ax.set_ylabel("AUC-ROC", fontsize=13)
    ax.set_title("Temporal AUC-ROC by Week", fontsize=15)
    ax.legend(fontsize=11)
    ax.set_ylim(0.4, 1.0)

    _save(fig, save_path or FIGURES_DIR / "temporal_auc")
    return fig


def plot_feature_importance(
    importances: np.ndarray,
    feature_names: list[str],
    model_name: str,
    save_path: Optional[Path | str] = None,
) -> plt.Figure:
    top_n = 15
    indices = np.argsort(importances)[-top_n:]
    top_names = [feature_names[i] for i in indices]
    top_scores = importances[indices]

    fig, ax = plt.subplots(figsize=_FIG_SIZE_DEFAULT)
    ax.barh(top_names, top_scores, color="steelblue")
    ax.set_xlabel("Importance", fontsize=12)
    ax.set_title(f"Top {top_n} Feature Importances — {model_name}", fontsize=14)
    ax.invert_yaxis()

    _save(fig, save_path or FIGURES_DIR / f"feature_importance_{model_name}")
    return fig


def plot_confusion_matrix(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    model_name: str,
    save_path: Optional[Path | str] = None,
) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(8, 6))
    disp = ConfusionMatrixDisplay.from_predictions(
        y_true,
        y_pred,
        display_labels=["Not At Risk", "At Risk"],
        colorbar=False,
        ax=ax,
        cmap="Blues",
    )
    ax.set_title(f"Confusion Matrix — {model_name}", fontsize=14)

    _save(fig, save_path or FIGURES_DIR / f"confusion_matrix_{model_name}")
    return fig


def plot_roc_curve(
    results_dict: dict[str, tuple[np.ndarray, np.ndarray, float]],
    save_path: Optional[Path | str] = None,
) -> plt.Figure:
    fig, ax = plt.subplots(figsize=_FIG_SIZE_DEFAULT)
    ax.plot([0, 1], [0, 1], "k--", linewidth=1, label="Random (AUC = 0.50)")

    for model_name, (y_true, y_prob, auc_score) in results_dict.items():
        fpr, tpr, _ = roc_curve(y_true, y_prob)
        ax.plot(fpr, tpr, linewidth=2, label=f"{model_name} (AUC = {auc_score:.3f})")

    ax.set_xlabel("False Positive Rate", fontsize=13)
    ax.set_ylabel("True Positive Rate", fontsize=13)
    ax.set_title("ROC Curves — Model Comparison", fontsize=15)
    ax.legend(fontsize=11, loc="lower right")

    _save(fig, save_path or FIGURES_DIR / "roc_curves")
    return fig
