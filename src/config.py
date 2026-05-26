"""Central configuration: paths, seeds, and model hyperparameters for EduForecast."""

from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR: Path = Path(__file__).resolve().parent.parent

DATA_DIR: Path = BASE_DIR / "data"
RAW_DIR: Path = DATA_DIR / "raw"
PROCESSED_DIR: Path = DATA_DIR / "processed"

RESULTS_DIR: Path = BASE_DIR / "results"
FIGURES_DIR: Path = RESULTS_DIR / "figures"
METRICS_DIR: Path = RESULTS_DIR / "metrics"

# Ensure output directories exist at import time
for _dir in (PROCESSED_DIR, FIGURES_DIR, METRICS_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

# ── Experiment settings ────────────────────────────────────────────────────────
RANDOM_SEED: int = 42
TEST_SIZE: float = 0.2
VAL_SIZE: float = 0.1

# ── Target ────────────────────────────────────────────────────────────────────
TARGET_COLUMN: str = "is_at_risk"

# OULAD spans 39 weeks of VLE interaction data
WEEKS_RANGE: list[int] = list(range(1, 40))

# ── Model hyperparameters ──────────────────────────────────────────────────────
MODEL_PARAMS: dict = {
    "random_forest": {
        "n_estimators": 200,
        "max_depth": 10,
        "random_state": RANDOM_SEED,
    },
    "lstm": {
        "hidden_size": 64,
        "num_layers": 2,
        "dropout": 0.2,
        "learning_rate": 0.001,
        "epochs": 30,
        "batch_size": 64,
    },
    "tft": {
        "hidden_size": 64,
        "attention_head_size": 4,
        "dropout": 0.1,
        "learning_rate": 0.001,
        "epochs": 30,
        "batch_size": 64,
    },
}
