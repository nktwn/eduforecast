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


def test_two_way_fe_matches_dummy_regression():
    from src.finance.budget_outcomes import fe_ols, holm

    rng = np.random.default_rng(0)
    rows = [(i, t) for i in range(40) for t in range(2012, 2020) if rng.random() > 0.2]
    d = pd.DataFrame(rows, columns=["series_id", "year"])
    a = rng.normal(size=40)[d["series_id"]]
    g = rng.normal(size=8)[d["year"] - 2012]
    d["x"] = rng.normal(size=len(d)) + 0.5 * a
    d["y"] = 0.7 * d["x"] + a + g + rng.normal(size=len(d))
    res = fe_ols(d, "y", ["x"])

    dummies = pd.get_dummies(d[["series_id", "year"]].astype(str), drop_first=False, dtype=float)
    X = np.column_stack([d["x"], dummies.drop(columns=["year_2012"])])
    coef, *_ = np.linalg.lstsq(X, d["y"], rcond=None)
    assert abs(coef[0] - res["beta"]) < 1e-8
    u = d["y"].to_numpy() - X @ coef
    xt = X[:, 0] - X[:, 1:] @ np.linalg.lstsq(X[:, 1:], X[:, 0], rcond=None)[0]
    meat = sum((xt[d["series_id"] == s] @ u[d["series_id"] == s]) ** 2 for s in d["series_id"].unique())
    assert abs(meat / (xt @ xt) ** 2 - res["unscaled_vcov"][0, 0]) < 1e-10

    assert holm([0.01, 0.04, 0.03, 0.5]) == [0.04, 0.09, 0.09, 0.5]
