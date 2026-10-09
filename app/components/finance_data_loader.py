import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

from src.finance.api.contract import CONTRACT_VERSION, validate
from src.finance.api.providers import DemoProvider, MockProvider

PROVIDERS = {"demo": "Демо-модель (LightGBM)", "mock": "Мок (синтетика)"}


@st.cache_resource(show_spinner="Загрузка панели IPEDS и демо-модели...")
def get_provider(name: str):
    return DemoProvider() if name == "demo" else MockProvider()


@st.cache_data(show_spinner=False)
def search(name: str, query: str) -> list[dict]:
    return get_provider(name).search(query, limit=50)


@st.cache_data(show_spinner="Расчёт прогноза...")
def forecast(name: str, series_id: int) -> tuple[dict, list[str]]:
    response = get_provider(name).forecast(series_id)
    return response, validate(response)


__all__ = ["CONTRACT_VERSION", "PROVIDERS", "forecast", "get_provider", "search"]
