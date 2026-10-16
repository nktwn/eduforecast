"""Lagged features for the stage-2 panel.

A lag k of a column is its value in year t-k of the same series_id. It is taken only
from that exact year (no forward/backward filling across gaps), so a feature at year t
never uses data from years > t.
"""
import pandas as pd

LAGS = (1, 2, 3)


def add_lags(frame: pd.DataFrame, cols: list[str], lags=LAGS, key: str = "series_id") -> pd.DataFrame:
    out = frame.copy()
    base = frame[[key, "year"] + cols]
    for k in lags:
        shifted = base.assign(year=base["year"] + k).rename(columns={c: f"{c}_lag{k}" for c in cols})
        out = out.merge(shifted, on=[key, "year"], how="left")
    return out


def add_window_mean(frame: pd.DataFrame, col: str, start: int, end: int, key: str = "series_id",
                    min_years: int | None = None) -> pd.Series:
    """Mean of `col` over years t-start..t-end (start >= end >= 0) of the same series.

    Used for the cohort-window share of expenses (t-5..t) in the stage-4 description.
    """
    span = start - end + 1
    min_years = span if min_years is None else min_years
    parts = []
    base = frame[[key, "year", col]]
    for k in range(end, start + 1):
        parts.append(base.assign(year=base["year"] + k)[[key, "year", col]].rename(columns={col: f"_w{k}"}))
    merged = frame[[key, "year"]]
    for part in parts:
        merged = merged.merge(part, on=[key, "year"], how="left")
    vals = merged[[f"_w{k}" for k in range(end, start + 1)]]
    return vals.mean(axis=1).where(vals.notna().sum(axis=1) >= min_years).set_axis(frame.index)
