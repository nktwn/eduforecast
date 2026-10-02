import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

from src.research.aggregate import build_yearly_counts, filter_training_window
from src.research.config import OPENALEX_INSTITUTION_NAME, TRAINING_YEAR_MAX, TRAINING_YEAR_MIN
from src.research.forecast import ForecastComparison, run_forecast_comparison


@st.cache_data(show_spinner="Загрузка данных OpenAlex...", ttl=86400)
def load_yearly_counts():
    full = build_yearly_counts()
    training = filter_training_window(full)
    return full, training


@st.cache_data(show_spinner="Построение прогноза (Prophet)...")
def get_forecast_comparison() -> ForecastComparison:
    _, training = load_yearly_counts()
    return run_forecast_comparison(training)


INSTITUTION_NAME = OPENALEX_INSTITUTION_NAME
TRAINING_WINDOW = (TRAINING_YEAR_MIN, TRAINING_YEAR_MAX)
