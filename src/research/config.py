"""Central configuration for the Research (scientific productivity) module."""

from pathlib import Path

from src.config import BASE_DIR, RESULTS_DIR

# -- Paths --------------------------------------------------------------------
RESEARCH_DATA_DIR: Path = BASE_DIR / "data" / "research"
RAW_DIR: Path = RESEARCH_DATA_DIR / "raw"
PROCESSED_DIR: Path = RESEARCH_DATA_DIR / "processed"

RESEARCH_RESULTS_DIR: Path = RESULTS_DIR / "research"
FIGURES_DIR: Path = RESEARCH_RESULTS_DIR / "figures"
METRICS_DIR: Path = RESEARCH_RESULTS_DIR / "metrics"

for _dir in (RAW_DIR, PROCESSED_DIR, FIGURES_DIR, METRICS_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

# -- OpenAlex source --------------------------------------------------------
# Resolved by a one-off manual lookup (see PROJECT_STATUS.md §4.4):
# GET https://api.openalex.org/institutions?search=Astana IT University
# returned exactly one unambiguous match.
OPENALEX_INSTITUTION_ID: str = "I4405257690"
OPENALEX_INSTITUTION_NAME: str = "Astana IT University"
OPENALEX_API_BASE: str = "https://api.openalex.org"

# -- Training window ----------------------------------------------------------
# 2019 is excluded on purpose: the institution has a single indexed publication
# that year (pre-registration / startup period), which is not representative
# of an actual annual publication rate and would distort both the trend fit
# and the logistic growth cap below.
TRAINING_YEAR_MIN: int = 2020
TRAINING_YEAR_MAX: int = 2026

# -- Logistic growth cap --------------------------------------------------
# Prophet's growth='logistic' requires a saturating capacity ("cap"). There is
# no data-driven way to derive this from 7 yearly points, so this is an
# explicit EXPERT GUESS, not a value inferred from the series:
# current observed peak (2026: 753 works) x 2 as a plausible near-term
# ceiling for a still-growing young university. Treat this as a modelling
# assumption to sanity-check/revise once a few more years of data exist.
LOGISTIC_CAP_MULTIPLIER: float = 2.0
