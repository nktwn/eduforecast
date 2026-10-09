import argparse
import logging
import warnings

import numpy as np
import pandas as pd

from src.research.config import METRICS_DIR, PANEL_PATH, PANEL_YEAR_MAX

TARGETS = {
    "works_count": "count",
    "citations_received_in_year": "count",
    "unique_authors": "count",
    "intl_collab_share": "share",
    "top10_share": "share",
    "fwci_mean": "positive",
    "oa_share": "share",
}
MODELS = ("naive", "linear_trend", "prophet")
SERIES_START_MIN_WORKS = 10
MIN_TRAIN_YEARS = 3
COMMON_WINDOW = (2021, PANEL_YEAR_MAX)


def smape(actual: np.ndarray, pred: np.ndarray) -> float:
    actual, pred = np.asarray(actual, float), np.asarray(pred, float)
    denom = np.abs(actual) + np.abs(pred)
    ratio = np.where(denom == 0, 0.0, 2 * np.abs(actual - pred) / np.where(denom == 0, 1, denom))
    return float(ratio.mean() * 100)


def _clip(value: float, kind: str) -> float:
    if kind == "share":
        return float(np.clip(value, 0, 1))
    return float(max(value, 0))


def predict_naive(years: np.ndarray, values: np.ndarray, target_year: int) -> float:
    return float(values[-1])


def predict_linear(years: np.ndarray, values: np.ndarray, target_year: int) -> float:
    slope, intercept = np.polyfit(years, values, 1)
    return float(slope * target_year + intercept)


def predict_prophet(years: np.ndarray, values: np.ndarray, target_year: int) -> float:
    from prophet import Prophet

    model = Prophet(
        growth="linear",
        yearly_seasonality=False,
        weekly_seasonality=False,
        daily_seasonality=False,
        n_changepoints=min(5, len(years) - 2),
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model.fit(pd.DataFrame({"ds": pd.to_datetime(years.astype(str), format="%Y"), "y": values}))
    future = pd.DataFrame({"ds": pd.to_datetime([str(target_year)], format="%Y")})
    return float(model.predict(future)["yhat"].iloc[0])


PREDICTORS = {"naive": predict_naive, "linear_trend": predict_linear, "prophet": predict_prophet}


def series_start(uni_panel: pd.DataFrame) -> int:
    active = uni_panel.loc[uni_panel["works_count"] >= SERIES_START_MIN_WORKS, "year"]
    return int(active.min())


def rolling_origin_backtest(panel: pd.DataFrame, models=MODELS) -> pd.DataFrame:
    logging.getLogger("cmdstanpy").setLevel(logging.WARNING)
    logging.getLogger("prophet").setLevel(logging.WARNING)
    panel = panel[(~panel["is_partial"]) & (panel["year"] <= PANEL_YEAR_MAX)]

    rows = []
    for uni, g in panel.groupby("uni"):
        g = g.sort_values("year")
        g = g[g["year"] >= series_start(g)]
        for target, kind in TARGETS.items():
            s = g[["year", target]].dropna()
            years, values = s["year"].to_numpy(), s[target].to_numpy(float)
            for i in range(MIN_TRAIN_YEARS, len(years)):
                for model in models:
                    pred = _clip(PREDICTORS[model](years[:i], values[:i], int(years[i])), kind)
                    rows.append({
                        "uni": uni, "target": target, "model": model,
                        "origin": int(years[i - 1]), "year": int(years[i]),
                        "actual": values[i], "pred": pred,
                    })
    return pd.DataFrame(rows)


def summarize(preds: pd.DataFrame, window: tuple[int, int] | None = None) -> pd.DataFrame:
    if window is not None:
        preds = preds[preds["year"].between(*window)]
    per_uni = (
        preds.groupby(["target", "model", "uni"])
        .apply(lambda d: pd.Series({
            "n_folds": len(d),
            "MAE": float(np.abs(d["actual"] - d["pred"]).mean()),
            "sMAPE": smape(d["actual"], d["pred"]),
        }), include_groups=False)
        .reset_index()
    )
    return per_uni


def macro_average(per_uni: pd.DataFrame) -> pd.DataFrame:
    return (
        per_uni.groupby(["target", "model"])
        .agg(n_unis=("uni", "nunique"), n_folds=("n_folds", "sum"), MAE=("MAE", "mean"), sMAPE=("sMAPE", "mean"))
        .reset_index()
    )


def main():
    parser = argparse.ArgumentParser(description="Naive / linear / Prophet rolling-origin backtest, horizon 1 year")
    parser.add_argument("--models", nargs="*", default=list(MODELS))
    args = parser.parse_args()

    panel = pd.read_parquet(PANEL_PATH)
    preds = rolling_origin_backtest(panel, args.models)
    preds.to_csv(METRICS_DIR / "baseline_predictions.csv", index=False)

    per_uni = summarize(preds)
    per_uni.to_csv(METRICS_DIR / "baseline_per_uni.csv", index=False)
    macro_average(per_uni).to_csv(METRICS_DIR / "baseline_summary.csv", index=False)

    common = summarize(preds, COMMON_WINDOW)
    common.to_csv(METRICS_DIR / "baseline_per_uni_common_window.csv", index=False)
    summary_common = macro_average(common)
    summary_common.to_csv(METRICS_DIR / "baseline_summary_common_window.csv", index=False)
    print(summary_common.to_string(index=False))


if __name__ == "__main__":
    main()
