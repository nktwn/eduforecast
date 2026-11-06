import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import streamlit as st

from src.finance import aitu_profile, rules
from src.finance.api.contract import CONTRACT_VERSION, validate
from src.finance.api.demo_model import META_PATH
from src.finance.api.providers import DemoProvider, MockProvider
from src.finance.config import PANEL_PATH
from src.finance.models_stage2 import MODEL_DIR, OUT_DIR as STAGE2_DIR
from src.finance.panel_stage2 import PANEL2_PATH

PROVIDERS = {"stage2": "Модель этапа 2 (оценена по критерию)", "demo": "Демо-модель (не оценена)",
             "mock": "Мок (синтетика)"}
REQUIRED = {"stage2": [PANEL_PATH, PANEL2_PATH, MODEL_DIR / "deploy_meta.json"], "demo": [PANEL_PATH, META_PATH],
            "mock": []}


def missing(name: str) -> list[Path]:
    return [p for p in REQUIRED[name] if not p.exists()]


@st.cache_resource(show_spinner="Загрузка панели IPEDS и модели...")
def get_provider(name: str):
    if name == "stage2":
        from src.finance.api.stage2_provider import Stage2Provider
        return Stage2Provider()
    return DemoProvider() if name == "demo" else MockProvider()


@st.cache_data(show_spinner=False)
def search(name: str, query: str) -> list[dict]:
    return get_provider(name).search(query, limit=50)


@st.cache_data(show_spinner="Расчёт прогноза...")
def forecast(name: str, series_id: int) -> tuple[dict, list[str]]:
    response = get_provider(name).forecast(series_id)
    return response, validate(response)


@st.cache_data(show_spinner=False)
def stage2_table(name: str) -> pd.DataFrame | None:
    path = STAGE2_DIR / name
    return pd.read_csv(path) if path.exists() else None


@st.cache_data(show_spinner=False)
def aitu() -> dict:
    df = aitu_profile.load()
    panel = pd.read_parquet(PANEL2_PATH) if PANEL2_PATH.exists() else None
    structure = aitu_profile.structure(df)
    return {"raw": df, "checks": aitu_profile.sum_checks(df), "structure": structure,
            "structure_excl": aitu_profile.structure(df, exclude_one_off=True),
            "rules": rules.evaluate_variants(df, panel), "us_data": panel is not None}


__all__ = ["CONTRACT_VERSION", "PROVIDERS", "aitu", "forecast", "get_provider", "missing", "search", "stage2_table"]
