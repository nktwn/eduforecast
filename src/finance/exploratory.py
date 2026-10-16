"""Exploratory analyses added AFTER the main (pre-registered) run. Not part of the criterion.

Baseline "3-year moving average" on exactly the criterion points (same errors, sample and
bootstrap as src/finance/criterion.py):
- level targets (retention, graduation rates): forecast = mean of the values in years t-2..t;
- log targets (enrollment, real core expenses per FTE): forecast = z_t + mean of the year-on-year
  changes in t-2..t (changes t-3->t-2, t-2->t-1, t-1->t).
Only values from those exact years of the same series are used; if fewer than 3 exist, the mean of
the available ones (the value z_t always exists; with no change available the forecast is naive).

  python -m src.finance.exploratory
"""
import numpy as np
import pandas as pd

from src.finance import criterion_stage2 as C
from src.finance.baseline import _series, bootstrap_gain
from src.finance.config import PANEL_PATH
from src.finance.features_stage2 import add_lags
from src.finance.models_stage2 import OUT_DIR

LABEL = "исследовательские (после основного прогона)"
COMPARED = ["lgbm_S3", "ridge_S1", "ridge_S3"]


def ma3_forecasts(panel: pd.DataFrame, target: str) -> pd.DataFrame:
    """(series_id, target_year) -> MA3 forecast of z for target_year from data up to target_year-1."""
    s = _series(panel, target)[["series_id", "year", "z", "change"]]
    s = add_lags(s, ["z", "change"], lags=(1, 2))
    if C.TARGETS[target]["kind"] == "level":
        fc = s[["z", "z_lag1", "z_lag2"]].mean(axis=1)
        n = s[["z", "z_lag1", "z_lag2"]].notna().sum(axis=1)
    else:
        mean_change = s[["change", "change_lag1", "change_lag2"]].mean(axis=1)
        n = s[["change", "change_lag1", "change_lag2"]].notna().sum(axis=1)
        fc = s["z"] + mean_change.fillna(0.0)
    return pd.DataFrame({"series_id": s["series_id"], "target_year": s["year"] + 1, "forecast_ma3": fc,
                         "ma3_n_years": n})


def compare(panel: pd.DataFrame) -> pd.DataFrame:
    preds = pd.read_parquet(OUT_DIR / "rolling_predictions.parquet")
    rows = []
    for target in C.TARGET_LIST:
        p = preds[(preds["target"] == target) & preds["model"].isin(COMPARED)]
        ma = ma3_forecasts(panel, target)
        p = p.merge(ma, on=["series_id", "target_year"], how="left", validate="many_to_one")
        assert p["forecast_ma3"].notna().all(), target
        p["err_ma3"] = (p["forecast_ma3"] - p["z"]).abs()
        base = p[p["model"] == COMPARED[0]]
        for scope in C.EVAL_SCOPES:
            q = base if scope == "all_years" else base[~base["flagged"]]
            per = q.groupby("series_id")[["err_ma3", "err_naive"]].mean().rename(columns={"err_ma3": "err_model"})
            rows.append({"target": target, "scope": scope, "comparison": "MA3 vs naive", "n_points": len(q),
                         "full_3y_window_share": float((q["ma3_n_years"] == 3).mean()),
                         **bootstrap_gain(per, "model", np.random.default_rng(C.RANDOM_SEED))})
            for model in COMPARED:
                m = p[p["model"] == model]
                m = m if scope == "all_years" else m[~m["flagged"]]
                per = m.groupby("series_id")[["err_model", "err_ma3"]].mean().rename(columns={"err_ma3": "err_naive"})
                rows.append({"target": target, "scope": scope, "comparison": f"{model} vs MA3", "n_points": len(m),
                             **bootstrap_gain(per, "model", np.random.default_rng(C.RANDOM_SEED))})
    out = pd.DataFrame(rows).rename(columns={"MAE_naive": "MAE_reference", "gain_vs_naive": "gain_vs_reference",
                                             "institutions_beating_naive": "institutions_beating_reference",
                                             "meets_success_rule": "meets_rule_vs_reference"})
    out.insert(0, "label", LABEL)
    return out


def main():
    res = compare(pd.read_parquet(PANEL_PATH))
    res.to_csv(OUT_DIR / "exploratory_ma3.csv", index=False)
    pd.set_option("display.width", 250)
    print(res[["target", "scope", "comparison", "n_points", "MAE_reference", "MAE_model", "gain_vs_reference",
               "diff_ci_lo", "diff_ci_hi", "meets_rule_vs_reference"]].round(4).to_string(index=False))


if __name__ == "__main__":
    main()
