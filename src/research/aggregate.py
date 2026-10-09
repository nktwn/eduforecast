import pandas as pd

from src.research.config import PARTIAL_YEAR, TRAINING_YEAR_MAX, TRAINING_YEAR_MIN
from src.research.openalex_client import fetch_yearly_work_counts


def build_yearly_counts(raw: dict | None = None) -> pd.DataFrame:
    if raw is None:
        raw = fetch_yearly_work_counts()

    rows = [
        {"year": int(g["key"]), "works_count": int(g["count"])}
        for g in raw["group_by"]
    ]
    df = pd.DataFrame(rows).sort_values("year").reset_index(drop=True)
    df["is_partial"] = df["year"] >= PARTIAL_YEAR
    return df


def filter_training_window(
    df: pd.DataFrame,
    year_min: int = TRAINING_YEAR_MIN,
    year_max: int = TRAINING_YEAR_MAX,
) -> pd.DataFrame:
    mask = df["year"].between(year_min, year_max) & ~df["is_partial"]
    return df[mask].reset_index(drop=True)


def partial_years(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["is_partial"]].reset_index(drop=True)


def to_prophet_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame({
        "ds": pd.to_datetime(df["year"], format="%Y"),
        "y": df["works_count"].astype(float),
    })
    return out
