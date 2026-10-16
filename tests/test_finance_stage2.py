"""Finance stage 2: lags without look-ahead, schema checks (synthetic data, no IPEDS needed)."""
import numpy as np
import pandas as pd

from src.finance.features_stage2 import add_lags, add_window_mean
from src.finance.validate import SCHEMA, check_schema


def _frame():
    rows = [{"series_id": s, "year": y, "x": s * 100 + y} for s in (1, 2) for y in range(2010, 2018) if (s, y) != (2, 2013)]
    return pd.DataFrame(rows)


def test_lags_use_exact_past_year_only():
    f = add_lags(_frame(), ["x"])
    for _, r in f.iterrows():
        for k in (1, 2, 3):
            expected = r["series_id"] * 100 + r["year"] - k
            gap = r["series_id"] == 2 and r["year"] - k == 2013
            if r["year"] - k < 2010 or gap:
                assert np.isnan(r[f"x_lag{k}"])
            else:
                assert r[f"x_lag{k}"] == expected


def test_lags_ignore_future_changes():
    base = _frame()
    future = base.copy()
    future.loc[future["year"] > 2014, "x"] = -1
    a = add_lags(base, ["x"]).query("year <= 2014").reset_index(drop=True)
    b = add_lags(future, ["x"]).query("year <= 2014").reset_index(drop=True)
    pd.testing.assert_frame_equal(a, b)


def test_window_mean_covers_t_minus_5_to_t():
    f = _frame()
    m = add_window_mean(f, "x", start=5, end=0)
    row = f[(f.series_id == 1) & (f.year == 2016)].index[0]
    assert m[row] == np.mean([100 + y for y in range(2011, 2017)])
    assert np.isnan(m[f[(f.series_id == 1) & (f.year == 2014)].index[0]])


def test_schema_flags_out_of_range_and_duplicates():
    p = pd.DataFrame({c: [0.5, 0.5] for c in SCHEMA})
    p["unitid"], p["year"] = [100654, 100654], [2015, 2015]
    p["admit_rate"] = [0.5, 1.5]
    r = check_schema(p)
    assert ((r["column"] == "admit_rate") & (r["rule"] == "above_max")).any()
    assert (r["rule"] == "duplicate_key").any()
