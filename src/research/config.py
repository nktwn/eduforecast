from pathlib import Path

from src.config import BASE_DIR, RESULTS_DIR

RESEARCH_DATA_DIR: Path = BASE_DIR / "data" / "research"
RAW_DIR: Path = RESEARCH_DATA_DIR / "raw"
PROCESSED_DIR: Path = RESEARCH_DATA_DIR / "processed"

RESEARCH_RESULTS_DIR: Path = RESULTS_DIR / "research"
FIGURES_DIR: Path = RESEARCH_RESULTS_DIR / "figures"
METRICS_DIR: Path = RESEARCH_RESULTS_DIR / "metrics"

for _dir in (RAW_DIR, PROCESSED_DIR, FIGURES_DIR, METRICS_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

OPENALEX_INSTITUTION_ID: str = "I4405257690"
OPENALEX_INSTITUTION_NAME: str = "Astana IT University"
OPENALEX_API_BASE: str = "https://api.openalex.org"

TRAINING_YEAR_MIN: int = 2020
TRAINING_YEAR_MAX: int = 2026

LOGISTIC_CAP_MULTIPLIER: float = 2.0
