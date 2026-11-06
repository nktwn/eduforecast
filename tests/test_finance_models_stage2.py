"""Finance stage 3: no look-ahead in model features, data schema, criterion table reproduction.

These tests need the local IPEDS panel (data/finance, not in git) and are skipped without it.
"""
import numpy as np
import pandas as pd
import pytest

from src.finance.config import PANEL_PATH
from src.finance.panel_stage2 import PANEL2_PATH

pytestmark = pytest.mark.skipif(not (PANEL_PATH.exists() and PANEL2_PATH.exists()),
                                reason="needs data/finance/panel*.parquet")

# FINANCE_DATA_AUDIT.md §14: points, institutions and naive MAE of the F1 baseline.
CRITERION_TABLE = {
    ("core_total_per_fte_real", "all_years"): (15509, 1925, 0.09221),
    ("core_total_per_fte_real", "excluding_flagged"): (9805, 1916, 0.08894),
    ("fall_enrollment", "all_years"): (15917, 1985, 0.08403),
    ("fall_enrollment", "excluding_flagged"): (10069, 1976, 0.0813),
    ("grad_rate_150", "all_years"): (11564, 1429, 3.71),
    ("grad_rate_150", "excluding_flagged"): (7198, 1420, 3.722),
    ("retention_rate", "all_years"): (11634, 1424, 3.905),
    ("retention_rate", "excluding_flagged"): (7261, 1418, 3.605),
}


@pytest.fixture(scope="module")
def panel2():
    return pd.read_parquet(PANEL2_PATH)


def test_features_do_not_use_future_years(panel2):
    from src.finance.models_stage2 import common_features, target_frame
    from src.finance.criterion_stage2 import FEATURE_SETS

    cut = 2018
    future = panel2.copy()
    num = [c for c in future.select_dtypes("float").columns]
    rng = np.random.default_rng(0)
    late = future["year"] > cut
    future.loc[late, num] = future.loc[late, num] * rng.uniform(0.5, 1.5, size=(late.sum(), len(num)))
    feats = FEATURE_SETS["S3"]
    for target in ("retention_rate", "core_total_per_fte_real"):
        a = target_frame(panel2, common_features(panel2), target)
        b = target_frame(future, common_features(future), target)
        ya = a[a["year"] == cut].set_index("series_id")["y_next"]
        yb = b[b["year"] == cut].set_index("series_id")["y_next"]
        assert not np.allclose(ya.fillna(0), yb.reindex(ya.index).fillna(0))  # the label does see t+1: not vacuous
        a = a[a["year"] <= cut].set_index(["series_id", "year"])[feats].sort_index()
        b = b[b["year"] <= cut].set_index(["series_id", "year"])[feats].sort_index()
        pd.testing.assert_frame_equal(a, b)


def test_panel_schema_has_no_errors(panel2):
    from src.finance.validate import check_schema

    errors = check_schema(panel2)
    assert errors.empty, errors.to_string()


def test_criterion_table_reproduces(panel2):
    from src.finance.baseline import predictions
    from src.finance.criterion import TARGETS

    for target in TARGETS:
        p = predictions(pd.read_parquet(PANEL_PATH), target)
        for scope in ("all_years", "excluding_flagged"):
            q = p if scope == "all_years" else p[~p["flagged"]]
            per = q.groupby("series_id")["err_naive"].mean()
            n_points, n_inst, mae = CRITERION_TABLE[(target, scope)]
            assert (len(q), len(per)) == (n_points, n_inst)
            assert round(per.mean(), 5 if mae < 1 else 3) == pytest.approx(mae, abs=1e-5 if mae < 1 else 1e-3)


def test_moving_average_baseline_definition():
    from src.finance.baseline import _series
    from src.finance.exploratory import ma3_forecasts

    panel = pd.read_parquet(PANEL_PATH)
    for target in ("retention_rate", "fall_enrollment"):
        s = _series(panel, target).set_index(["series_id", "year"])
        ma = ma3_forecasts(panel, target).set_index(["series_id", "target_year"])
        sid = s.index.get_level_values(0)[1000]
        full = ma.loc[sid]
        y = 2018
        if target == "retention_rate":
            expected = np.mean([s.at[(sid, y - k), "z"] for k in range(3)])
        else:
            expected = s.at[(sid, y), "z"] + np.mean([s.at[(sid, y - k), "change"] for k in range(3)])
        assert full.at[y + 1, "forecast_ma3"] == pytest.approx(expected)
