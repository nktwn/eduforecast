import argparse
import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from lightgbm import LGBMRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from src.config import BASE_DIR
from src.research.config import PANEL_PATH, WORKS_DIR
from src.research.institutions import UNIVERSITIES
from src.research.stage2_config import (
    BASELINE,
    BOOTSTRAP_SAMPLES,
    CALIBRATION_ORIGINS,
    CONFORMAL_LEVELS,
    CONFORMAL_MIN_RESIDUALS,
    EVAL_ORIGINS,
    EXCLUDE_YEARS,
    FLAGGED_POINTS,
    INNER_VALIDATION_ORIGINS,
    LAST_COMPLETE_YEAR,
    LGBM_FIXED,
    LGBM_GRID,
    MODELS,
    N_GROWTH_LAGS,
    QUALITY_MAIN_MAX_TARGET_YEAR,
    RANDOM_SEED,
    RIDGE_GRID,
    SDU_MAIN_INCLUDED,
    SERIES_START_MIN_WORKS,
    STAGE2_DIR,
    SUCCESS_CI_LEVEL,
    SUCCESS_MIN_RELATIVE_MAE_GAIN,
    TARGETS,
)

FIG_DIR = BASE_DIR / "docs" / "stage2"
COUNTRIES = sorted({u.country for u in UNIVERSITIES})
SCENARIOS = {
    "main": {"include_sdu": SDU_MAIN_INCLUDED, "drop_flagged": False},
    "sens_no_kbtu2021": {"include_sdu": SDU_MAIN_INCLUDED, "drop_flagged": True},
    "sens_with_sdu": {"include_sdu": True, "drop_flagged": False},
}
ML_MODELS = ("ridge", "lgbm")


def load_panel(include_sdu: bool) -> pd.DataFrame:
    p = pd.read_parquet(PANEL_PATH)
    p = p[(~p["is_partial"]) & (p["year"] <= LAST_COMPLETE_YEAR)].copy()
    p["citations_per_author"] = p["citations_received_in_year"] / p["unique_authors"].replace(0, np.nan)
    for uni, years in EXCLUDE_YEARS.items():
        p = p[~((p["uni"] == uni) & p["year"].isin(list(years)))]
    if not include_sdu:
        p = p[p["uni"] != "SDU"]
    return p


def _series(g: pd.DataFrame, column: str, years: pd.Index) -> pd.Series:
    return g.set_index("year")[column].reindex(years)


def build_rows(panel: pd.DataFrame, target: str, drop_flagged: bool) -> pd.DataFrame:
    spec = TARGETS[target]
    is_count = spec["kind"] == "count"
    years = pd.Index(range(panel["year"].min(), LAST_COMPLETE_YEAR + 1), name="year")
    rows = []
    for uni, g in panel.groupby("uni"):
        works_all = _series(g, "works_count", years)
        start = works_all[works_all >= SERIES_START_MIN_WORKS].index.min()
        first_pub = int(g.loc[g["works_count_all"] > 0, "year"].min())
        country = g["country"].iloc[0]
        valid = years >= max(start, spec.get("min_year", start))

        def level(column):
            s = _series(g, column, years).where(valid)
            if drop_flagged:
                for f_uni, f_year in FLAGGED_POINTS:
                    if f_uni == uni and f_year in s.index:
                        s[f_year] = np.nan
            return s

        y = level(target)
        if is_count:
            y = y.where(y > 0)
            tr = np.log(y)
        else:
            tr = y
        growth = tr.diff()
        works = level("works_count").where(lambda s: s > 0)
        authors = level("unique_authors").where(lambda s: s > 0)
        works_g = np.log(works).diff()
        authors_g = np.log(authors).diff()

        for t in years[N_GROWTH_LAGS + 1:]:
            lags = [growth.get(t - k) for k in range(1, N_GROWTH_LAGS + 1)]
            row = {
                "uni": uni, "year": t, "country": country,
                "g": growth.get(t), "y": y.get(t), "y_prev": y.get(t - 1),
                **{f"g_lag{k}": lag for k, lag in enumerate(lags, start=1)},
                "drift3": float(np.mean(lags)),
                "level_lag1": tr.get(t - 1),
                "log_works_lag1": np.log(works.get(t - 1)),
                "works_g_lag1": works_g.get(t - 1),
                "authors_g_lag1": authors_g.get(t - 1),
                "age": (t - 1) - first_pub,
                "flagged": any((uni, yy) in FLAGGED_POINTS for yy in range(t - N_GROWTH_LAGS - 1, t + 1)),
            }
            for c in COUNTRIES:
                row[f"country_{c}"] = float(country == c)
            rows.append(row)

    df = pd.DataFrame(rows)
    needed = ["g", "y_prev", "drift3", "level_lag1", "log_works_lag1", "works_g_lag1", "authors_g_lag1"]
    return df.dropna(subset=needed).reset_index(drop=True)


def feature_columns(target: str) -> list[str]:
    cols = [f"g_lag{k}" for k in range(1, N_GROWTH_LAGS + 1)]
    cols += ["drift3", "level_lag1", "log_works_lag1", "age"]
    if target != "works_count":
        cols.append("works_g_lag1")
    if target not in ("unique_authors", "unique_authors_no_hyper"):
        cols.append("authors_g_lag1")
    cols += [f"country_{c}" for c in COUNTRIES]
    return cols


def make_model(model: str, params: dict):
    if model == "ridge":
        return make_pipeline(StandardScaler(), Ridge(**params))
    return LGBMRegressor(**LGBM_FIXED, **params, random_state=RANDOM_SEED, n_jobs=1)


def fit_predict(model: str, params: dict, train: pd.DataFrame, test: pd.DataFrame, cols: list[str]) -> np.ndarray:
    if model == "naive":
        return np.zeros(len(test))
    if model == "drift":
        return test["drift3"].to_numpy()
    est = make_model(model, params)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        est.fit(train[cols], train["g"])
        return est.predict(test[cols])


def tune(model: str, train: pd.DataFrame, cols: list[str]) -> dict:
    grid = RIDGE_GRID if model == "ridge" else LGBM_GRID
    last = int(train["year"].max())
    folds = []
    for inner_origin in range(last - INNER_VALIDATION_ORIGINS, last):
        tr = train[train["year"] <= inner_origin]
        va = train[train["year"] == inner_origin + 1]
        if len(tr) >= 20 and len(va) > 0:
            folds.append((tr, va))
    if not folds:
        return grid[len(grid) // 2]
    scores = []
    for params in grid:
        errors = np.concatenate([np.abs(fit_predict(model, params, tr, va, cols) - va["g"].to_numpy())
                                 for tr, va in folds])
        scores.append(errors.mean())
    return grid[int(np.argmin(scores))]


def _prediction_rows(test, model, scheme, g_pred, params, origin):
    out = test[["uni", "year", "g", "y", "y_prev", "flagged"]].copy()
    out["origin"] = origin
    out["model"] = model
    out["scheme"] = scheme
    out["g_pred"] = g_pred
    out["params"] = str(params) if params else ""
    return out


def run_target(target: str, scenario: str) -> pd.DataFrame:
    cfg = SCENARIOS[scenario]
    rows = build_rows(load_panel(cfg["include_sdu"]), target, cfg["drop_flagged"])
    if cfg["drop_flagged"]:
        rows = rows[~rows["flagged"]].reset_index(drop=True)
    cols = feature_columns(target)
    out = []
    for origin in CALIBRATION_ORIGINS + EVAL_ORIGINS:
        train = rows[rows["year"] <= origin]
        test = rows[rows["year"] == origin + 1]
        if test.empty or len(train) < 20:
            continue
        for model in MODELS:
            params = tune(model, train, cols) if model in ML_MODELS else {}
            out.append(_prediction_rows(test, model, "rolling", fit_predict(model, params, train, test, cols),
                                        params, origin))
        if origin not in EVAL_ORIGINS:
            continue
        for uni in test["uni"].unique():
            train_u = train[train["uni"] != uni]
            test_u = test[test["uni"] == uni]
            for model in MODELS:
                params = tune(model, train_u, cols) if model in ML_MODELS else {}
                out.append(_prediction_rows(test_u, model, "louo", fit_predict(model, params, train_u, test_u, cols),
                                            params, origin))
    preds = pd.concat(out, ignore_index=True)
    preds.insert(0, "target", target)
    preds.insert(0, "scenario", scenario)
    return preds


def to_level(preds: pd.DataFrame) -> pd.DataFrame:
    preds = preds.copy()
    is_count = preds["target"].map(lambda t: TARGETS[t]["kind"] == "count")
    preds["y_pred"] = np.where(is_count, preds["y_prev"] * np.exp(preds["g_pred"]),
                               np.clip(preds["y_prev"] + preds["g_pred"], 0, None))
    share = preds["target"].map(lambda t: t.endswith("_share"))
    preds.loc[share, "y_pred"] = preds.loc[share, "y_pred"].clip(upper=1)
    preds["err_g"] = np.where(is_count, np.abs(np.log(preds["y_pred"] / preds["y"])),
                              np.abs(preds["y_pred"] - preds["y"]))
    preds["err_level"] = np.abs(preds["y_pred"] - preds["y"])
    denom = np.abs(preds["y"]) + np.abs(preds["y_pred"])
    preds["smape"] = np.where(denom == 0, 0.0, 2 * preds["err_level"] / denom.replace(0, 1)) * 100
    return preds


def assign_subset(preds: pd.DataFrame) -> pd.DataFrame:
    preds = preds[preds["origin"].isin(EVAL_ORIGINS)].copy()
    quality = preds["target"].map(lambda t: TARGETS[t].get("quality", False))
    preds["subset"] = np.where(quality & (preds["year"] > QUALITY_MAIN_MAX_TARGET_YEAR), "preliminary", "main")
    return preds


def per_uni_metrics(preds: pd.DataFrame) -> pd.DataFrame:
    keys = ["scenario", "scheme", "target", "subset", "model", "uni"]
    m = preds.groupby(keys).agg(n=("err_g", "size"), MAE_growth=("err_g", "mean"),
                                MAE_level=("err_level", "mean"), sMAPE=("smape", "mean")).reset_index()
    naive = m[m["model"] == BASELINE].set_index(["scenario", "scheme", "target", "subset", "uni"])
    idx = m.set_index(["scenario", "scheme", "target", "subset", "uni"]).index
    naive_mae = naive.reindex(idx)["MAE_level"].to_numpy()
    m["MASE_vs_naive"] = m["MAE_level"].to_numpy() / np.where(naive_mae > 0, naive_mae, np.nan)
    return m


def _bootstrap(model_mae: np.ndarray, naive_mae: np.ndarray, rng) -> dict:
    n = len(model_mae)
    idx = rng.integers(0, n, size=(BOOTSTRAP_SAMPLES, n))
    m, b = model_mae[idx].mean(axis=1), naive_mae[idx].mean(axis=1)
    alpha = (1 - SUCCESS_CI_LEVEL) / 2
    diff_lo, diff_hi = np.quantile(m - b, [alpha, 1 - alpha])
    gain_lo, gain_hi = np.quantile(1 - m / b, [alpha, 1 - alpha])
    return {"diff_ci_lo": diff_lo, "diff_ci_hi": diff_hi, "gain_ci_lo": gain_lo, "gain_ci_hi": gain_hi}


def summarize(per_uni: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(RANDOM_SEED)
    rows = []
    for key, g in per_uni.groupby(["scenario", "scheme", "target", "subset"]):
        wide = g.pivot(index="uni", columns="model", values="MAE_growth").dropna()
        for model in MODELS:
            sub = g[g["model"] == model]
            row = dict(zip(["scenario", "scheme", "target", "subset"], key))
            row.update({
                "model": model, "n_unis": len(wide), "n_points": int(sub["n"].sum()),
                "MAE_growth": wide[model].mean(), "MAE_level": sub["MAE_level"].mean(),
                "sMAPE": sub["sMAPE"].mean(),
                "MASE_vs_naive_geomean": float(np.exp(np.log(sub["MASE_vs_naive"].replace(0, np.nan)).mean())),
                "MASE_undefined_unis": int(sub["MASE_vs_naive"].isna().sum()),
            })
            if model != BASELINE:
                m, b = wide[model].to_numpy(), wide[BASELINE].to_numpy()
                gain = 1 - m.mean() / b.mean()
                boot = _bootstrap(m, b, rng)
                row.update({
                    "gain_vs_naive": gain, "diff_vs_naive": m.mean() - b.mean(), **boot,
                    "diff_ci_width": boot["diff_ci_hi"] - boot["diff_ci_lo"],
                    "diff_ci_width_pct_of_naive": (boot["diff_ci_hi"] - boot["diff_ci_lo"]) / b.mean() * 100,
                    "unis_beating_naive": int((m < b).sum()),
                    "success": bool(gain >= SUCCESS_MIN_RELATIVE_MAE_GAIN and boot["diff_ci_hi"] < 0),
                })
            rows.append(row)
    return pd.DataFrame(rows)


def best_models(summary: pd.DataFrame) -> dict:
    main = summary[(summary["scenario"] == "main") & (summary["scheme"] == "rolling") & (summary["subset"] == "main")]
    best_any = main.loc[main.groupby("target")["MAE_growth"].idxmin()].set_index("target")["model"].to_dict()
    ml = main[main["model"].isin(ML_MODELS)]
    best_ml = ml.loc[ml.groupby("target")["MAE_growth"].idxmin()].set_index("target")["model"].to_dict()
    return {"any": best_any, "ml": best_ml}


def conformal(preds: pd.DataFrame, best: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    rolling = preds[(preds["scenario"] == "main") & (preds["scheme"] == "rolling")]
    intervals = []
    for target, model in best.items():
        p = rolling[(rolling["target"] == target) & (rolling["model"] == model)].copy()
        p["resid"] = np.abs(p["g"] - p["g_pred"])
        is_count = TARGETS[target]["kind"] == "count"
        for origin in EVAL_ORIGINS:
            calib = p.loc[p["year"] <= origin, "resid"].to_numpy()
            test = p[p["origin"] == origin]
            if len(calib) < CONFORMAL_MIN_RESIDUALS or test.empty:
                continue
            for level in CONFORMAL_LEVELS:
                q_level = min(1.0, np.ceil((len(calib) + 1) * level) / len(calib))
                q = np.quantile(calib, q_level, method="higher")
                lo_g, hi_g = test["g_pred"] - q, test["g_pred"] + q
                if is_count:
                    lo, hi = test["y_prev"] * np.exp(lo_g), test["y_prev"] * np.exp(hi_g)
                else:
                    lo, hi = (test["y_prev"] + lo_g).clip(0, 1), (test["y_prev"] + hi_g).clip(0, 1)
                intervals.append(pd.DataFrame({
                    "target": target, "model": model, "level": level, "origin": origin,
                    "uni": test["uni"], "year": test["year"], "y": test["y"], "y_pred": test["y_pred"],
                    "lo": lo, "hi": hi, "half_width_growth": q, "n_calib": len(calib),
                }))
    iv = pd.concat(intervals, ignore_index=True)
    iv["covered"] = (iv["y"] >= iv["lo"]) & (iv["y"] <= iv["hi"])
    iv["rel_width"] = (iv["hi"] - iv["lo"]) / iv["y"].abs().replace(0, np.nan)
    quality = iv["target"].map(lambda t: TARGETS[t].get("quality", False))
    iv["subset"] = np.where(quality & (iv["year"] > QUALITY_MAIN_MAX_TARGET_YEAR), "preliminary", "main")
    summary = iv.groupby(["target", "model", "subset", "level"]).agg(
        n=("covered", "size"), coverage=("covered", "mean"),
        median_half_width_growth=("half_width_growth", "median"),
        median_rel_width=("rel_width", "median")).reset_index()
    return iv, summary


def shap_importance(best_ml: dict) -> pd.DataFrame:
    import shap

    out = []
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    for target, best in best_ml.items():
        rows = build_rows(load_panel(SCENARIOS["main"]["include_sdu"]), target, False)
        cols = feature_columns(target)
        for model in ML_MODELS:
            params = tune(model, rows, cols)
            est = make_model(model, params)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                est.fit(rows[cols], rows["g"])
                if model == "lgbm":
                    values = shap.TreeExplainer(est).shap_values(rows[cols])
                    explainer = "TreeExplainer"
                else:
                    scaler, ridge = est[0], est[1]
                    x = pd.DataFrame(scaler.transform(rows[cols]), columns=cols)
                    values = shap.LinearExplainer(ridge, x).shap_values(x)
                    explainer = "LinearExplainer"
            imp = np.abs(values).mean(axis=0)
            direction = [np.corrcoef(rows[c], values[:, i])[0, 1] if rows[c].std() > 0 else np.nan
                         for i, c in enumerate(cols)]
            for c, v, d in zip(cols, imp, direction):
                out.append({"target": target, "model": model, "is_best_ml": model == best,
                            "explainer": explainer, "params": str(params), "feature": c,
                            "mean_abs_shap": v, "corr_feature_shap": d, "n_rows": len(rows)})
    shap_df = pd.DataFrame(out)
    _plot_shap(shap_df[shap_df["is_best_ml"]])
    return shap_df


def _plot_shap(df: pd.DataFrame):
    targets = list(df["target"].unique())
    fig, axes = plt.subplots(2, (len(targets) + 1) // 2, figsize=(16, 7))
    for ax, target in zip(axes.flat, targets):
        d = df[df["target"] == target].sort_values("mean_abs_shap").tail(8)
        ax.barh(d["feature"], d["mean_abs_shap"], color="#2a78d6", height=0.6)
        ax.set_title(f"{target}\n({d['model'].iloc[0]}, {d['explainer'].iloc[0]})", fontsize=9, loc="left")
        ax.tick_params(labelsize=8, length=0)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    for ax in list(axes.flat)[len(targets):]:
        ax.axis("off")
    fig.suptitle("Mean |SHAP| on the growth scale, best ML model per target (main sample)", x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "shap_importance.png", dpi=110)
    plt.close(fig)


def describe_by_type(panel: pd.DataFrame) -> pd.DataFrame:
    p = panel.sort_values(["uni", "year"]).copy()
    p["works_growth"] = np.log(p["works_count"].where(p["works_count"] > 0)).groupby(p["uni"]).diff()
    recent = p[p["year"].between(2021, LAST_COMPLETE_YEAR)]
    return recent.groupby("uni_type").agg(
        unis=("uni", "nunique"), median_works=("works_count", "median"),
        median_log_growth=("works_growth", "median"), median_intl_share=("intl_collab_share", "median"),
        median_top10_share=("top10_share", "median")).reset_index()


def turkish_coauthor_share() -> pd.DataFrame:
    rows = []
    for u in UNIVERSITIES:
        if u.country != "KZ":
            continue
        w = pd.read_parquet(WORKS_DIR / f"{u.key}.parquet")
        w = w[~(w["is_retracted"].fillna(False) | w["is_paratext"].fillna(False))]
        w = w[w["year"].between(2010, LAST_COMPLETE_YEAR)]
        share = w["countries"].map(lambda c: "TR" in c).groupby(w["year"]).mean()
        for year, v in share.items():
            rows.append({"uni": u.key, "year": year, "tr_coauthor_share": v})
    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser(description="Stage 2: growth models vs naive, rolling-origin + LOUO")
    parser.add_argument("--targets", nargs="*", default=list(TARGETS))
    parser.add_argument("--scenarios", nargs="*", default=list(SCENARIOS))
    parser.add_argument("--jobs", type=int, default=-1)
    args = parser.parse_args()

    jobs = [(t, s) for s in args.scenarios for t in args.targets]
    preds = pd.concat(Parallel(n_jobs=args.jobs)(delayed(run_target)(t, s) for t, s in jobs), ignore_index=True)
    preds = to_level(preds)
    preds.to_csv(STAGE2_DIR / "predictions_all_origins.csv", index=False)

    evaluated = assign_subset(preds)
    per_uni = per_uni_metrics(evaluated)
    per_uni.to_csv(STAGE2_DIR / "metrics_per_uni.csv", index=False)
    summary = summarize(per_uni)
    summary.to_csv(STAGE2_DIR / "summary.csv", index=False)

    best = best_models(summary)
    pd.DataFrame({"best_any": best["any"], "best_ml": best["ml"]}).rename_axis("target").to_csv(
        STAGE2_DIR / "best_models.csv")
    iv, cov = conformal(preds, best["any"])
    iv.to_csv(STAGE2_DIR / "conformal_intervals.csv", index=False)
    cov.to_csv(STAGE2_DIR / "conformal_coverage.csv", index=False)

    shap_importance(best["ml"]).to_csv(STAGE2_DIR / "shap_importance.csv", index=False)
    describe_by_type(load_panel(True)).to_csv(STAGE2_DIR / "descriptive_by_uni_type.csv", index=False)
    turkish_coauthor_share().to_csv(STAGE2_DIR / "tr_coauthor_share_kz.csv", index=False)

    cols = ["target", "model", "n_unis", "MAE_growth", "gain_vs_naive", "diff_ci_lo", "diff_ci_hi",
            "unis_beating_naive", "success"]
    view = summary[(summary["scenario"] == "main") & (summary["subset"] == "main")]
    for scheme in ("rolling", "louo"):
        print(f"\n== main / {scheme}")
        print(view[view["scheme"] == scheme][cols].round(4).to_string(index=False))


if __name__ == "__main__":
    main()
