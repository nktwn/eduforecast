"""Builds the yearly publication-count series used for forecasting."""

import pandas as pd

from src.research.config import TRAINING_YEAR_MAX, TRAINING_YEAR_MIN
from src.research.openalex_client import fetch_yearly_work_counts


def build_yearly_counts(raw: dict | None = None) -> pd.DataFrame:
    """Turns the OpenAlex group_by=publication_year response into a tidy,
    full (no implicit gaps) yearly DataFrame with columns: year, works_count."""
    if raw is None:
        raw = fetch_yearly_work_counts()

    rows = [
        {"year": int(g["key"]), "works_count": int(g["count"])}
        for g in raw["group_by"]
    ]
    df = pd.DataFrame(rows).sort_values("year").reset_index(drop=True)
    return df


def filter_training_window(
    df: pd.DataFrame,
    year_min: int = TRAINING_YEAR_MIN,
    year_max: int = TRAINING_YEAR_MAX,
) -> pd.DataFrame:
    """Restricts to [year_min, year_max]. Excludes 2019 by default — see
    config.TRAINING_YEAR_MIN docstring for why (pre-registration period,
    single publication, not representative of an annual rate)."""
    return df[(df["year"] >= year_min) & (df["year"] <= year_max)].reset_index(drop=True)


def to_prophet_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Prophet requires columns ds (datetime) and y (value)."""
    out = pd.DataFrame({
        "ds": pd.to_datetime(df["year"], format="%Y"),
        "y": df["works_count"].astype(float),
    })
    return out
