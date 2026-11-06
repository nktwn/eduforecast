"""Research stage 3: models on the extended panel by the pre-registration src/research/criterion_stage3.py.

  python -m src.research.stage3 run        # rolling + LOUO, extended panel and the 13 stage-2 universities
  python -m src.research.stage3 report     # criteria C1/C2, per-university tables, conformal, SHAP, AITU
"""
import argparse
import json
import warnings

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from lightgbm import LGBMRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from src.research import criterion_stage3 as C
from src.research.config import RESEARCH_RESULTS_DIR
from src.research.panel_stage3 import PANEL3_PATH
from src.research.stage2_config import N_GROWTH_LAGS, QUALITY_MAIN_MAX_TARGET_YEAR, SERIES_START_MIN_WORKS
from src.research.stage2_config import TARGETS as S2_TARGETS

OUT = RESEARCH_RESULTS_DIR / "stage3"
OUT.mkdir(parents=True, exist_ok=True)
STAGE2_13 = ["NU", "KBTU", "SATBAYEV", "KAZNU", "ENU", "NARXOZ", "KIMEP", "SHAKARIM", "AITU", "SKOLTECH",
             "INNOPOLIS", "UNIST", "MBZUAI"]
PANELS = ("extended", "orig13", "extended_with_sdu")
ML = ("ridge", "lgbm")
BASELINES_C2 = ("panel_mean", "age_mean")
AGE_MIN_POINTS = 5


def load(panel_name: str) -> pd.DataFrame:
    p = pd.read_parquet(PANEL3_PATH)
    p = p[p["year"].between(*C.PANEL_YEARS)].copy()
    if panel_name == "orig13":
        p = p[p["uni"].isin(STAGE2_13)]           # the 13 stage-2 universities, as in stage 2 (AITU, MBZUAI incl.)
    elif panel_name == "extended":
        p = p[p["role"] == "main"]
    else:
        p = p[p["role"].isin(["main", "sensitivity"])]
        p = p[~((p["uni"] == "SDU") & (p["year"] < 2017))]
    return p


def age_group(age: float) -> str:
    for name, (lo, hi) in C.AGE_GROUPS.items():
        if lo <= age <= hi:
            return name
    return "1-3"


def build_rows(panel: pd.DataFrame, target: str) -> pd.DataFrame:
    spec = C.TARGETS[target]
    is_count = spec["kind"] == "count"
    years = pd.Index(range(C.PANEL_YEARS[0], C.PANEL_YEARS[1] + 1), name="year")
    countries = sorted(panel["country"].unique())
    rows = []
    for uni, g in panel.groupby("uni"):
        gi = g.set_index("year")
        works = gi["works_count"].reindex(years)
        start = works[works >= SERIES_START_MIN_WORKS].index.min()
        if pd.isna(start):
            continue
        valid = years >= max(start, spec.get("min_year", start))
        y = gi[target].reindex(years).where(valid)
        tr = np.log(y.where(y > 0)) if is_count else y
        growth = tr.diff()
        w = works.where(valid & (works > 0))
        a = gi["unique_authors"].reindex(years).where(valid)
        a = a.where(a > 0)
        wg, ag = np.log(w).diff(), np.log(a).diff()
        country = g["country"].iloc[0]
        first_pub = int(g.loc[g["works_count_all"] > 0, "year"].min())
        for t in years[N_GROWTH_LAGS + 1:]:
            lags = [growth.get(t - k) for k in range(1, N_GROWTH_LAGS + 1)]
            series_age = t - start + 1                 # AGE_RULE (grouping for the age_mean baseline)
            row = {"uni": uni, "year": t, "country": country, "g": growth.get(t), "y": y.get(t),
                   "y_prev": y.get(t - 1), **{f"g_lag{k}": v for k, v in enumerate(lags, start=1)},
                   "drift3": float(np.mean(lags)), "level_lag1": tr.get(t - 1), "log_works_lag1": np.log(w.get(t - 1)),
                   "works_g_lag1": wg.get(t - 1), "authors_g_lag1": ag.get(t - 1),
                   "age": (t - 1) - first_pub,              # stage-2 feature definition
                   "age_group": age_group(series_age), "size": float(works.loc[C.PANEL_YEARS[0]:].median())}
            for c in countries:
                row[f"country_{c}"] = float(country == c)
            rows.append(row)
    df = pd.DataFrame(rows)
    need = ["g", "y_prev", "drift3", "level_lag1", "log_works_lag1", "works_g_lag1", "authors_g_lag1"]
    return df.dropna(subset=need).reset_index(drop=True)


def features(target: str, rows: pd.DataFrame) -> list[str]:
    cols = [f"g_lag{k}" for k in range(1, N_GROWTH_LAGS + 1)] + ["drift3", "level_lag1", "log_works_lag1", "age"]
    if target != "works_count":
        cols.append("works_g_lag1")
    if target != "unique_authors":
        cols.append("authors_g_lag1")
    return cols + [c for c in rows.columns if c.startswith("country_")]


def _est(model, params):
    if model == "ridge":
        return make_pipeline(StandardScaler(), Ridge(**params))
    return LGBMRegressor(**C.LGBM_FIXED, **params, random_state=C.RANDOM_SEED, n_jobs=1)


def predict(model, params, train, test, cols):
    if model == "naive":
        return np.zeros(len(test))
    if model == "drift3":
        return test["drift3"].to_numpy()
    if model == "panel_mean":
        return np.full(len(test), train["g"].mean())
    if model == "age_mean":
        means = train.groupby("age_group")["g"].agg(["mean", "size"])
        fallback = train["g"].mean()
        return np.array([means.at[a, "mean"] if a in means.index and means.at[a, "size"] >= AGE_MIN_POINTS
                         else fallback for a in test["age_group"]])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        est = _est(model, params).fit(train[cols], train["g"])
        return est.predict(test[cols])


def tune(model, train, cols):
    grid = C.RIDGE_GRID if model == "ridge" else C.LGBM_GRID
    last = int(train["year"].max())
    folds = [(train[train["year"] <= o], train[train["year"] == o + 1])
             for o in range(last - C.INNER_VALIDATION_ORIGINS, last)]
    folds = [(a, b) for a, b in folds if len(a) >= 20 and len(b)]
    if not folds:
        return grid[len(grid) // 2]
    scores = [np.mean(np.concatenate([np.abs(predict(model, p, a, b, cols) - b["g"].to_numpy()) for a, b in folds]))
              for p in grid]
    return grid[int(np.argmin(scores))]


def _block(train, test, cols, scheme, origin):
    out = []
    for model in C.MODELS:
        params = tune(model, train, cols) if model in ML else {}
        r = test[["uni", "year", "g", "y", "y_prev", "size", "age_group"]].copy()
        r["g_pred"], r["model"], r["scheme"], r["origin"], r["params"] = (
            predict(model, params, train, test, cols), model, scheme, origin, json.dumps(params))
        out.append(r)
    return pd.concat(out)


def run_target(panel_name, target):
    rows = build_rows(load(panel_name), target)
    cols = features(target, rows)
    jobs = []
    for origin in C.CALIBRATION_ORIGINS + C.EVAL_ORIGINS:
        train, test = rows[rows["year"] <= origin], rows[rows["year"] == origin + 1]
        if test.empty or len(train) < 20:
            continue
        jobs.append((train, test, "rolling", origin))
        if origin in C.EVAL_ORIGINS:
            for uni in test["uni"].unique():
                jobs.append((train[train["uni"] != uni], test[test["uni"] == uni], "louo", origin))
    parts = Parallel(n_jobs=-1)(delayed(_block)(tr, te, cols, s, o) for tr, te, s, o in jobs)
    out = pd.concat(parts, ignore_index=True)
    out.insert(0, "target", target)
    out.insert(0, "panel", panel_name)
    return out


def to_errors(p: pd.DataFrame) -> pd.DataFrame:
    count = p["target"].map(lambda t: C.TARGETS[t]["kind"] == "count")
    p["y_pred"] = np.where(count, p["y_prev"] * np.exp(p["g_pred"]), np.clip(p["y_prev"] + p["g_pred"], 0, 1))
    p["err_g"] = np.where(count, np.abs(np.log(p["y_pred"] / p["y"])), np.abs(p["y_pred"] - p["y"]))
    p["err_level"] = np.abs(p["y_pred"] - p["y"])
    return p


def run():
    allp = []
    for panel_name in PANELS:
        for target in C.TARGETS:
            allp.append(run_target(panel_name, target))
            print(panel_name, target, "done", flush=True)
    preds = to_errors(pd.concat(allp, ignore_index=True))
    preds.to_parquet(OUT / "predictions.parquet", index=False)


# ── criteria ──────────────────────────────────────────────────────────────────────────

def per_uni(preds):
    ev = preds[preds["origin"].isin(C.EVAL_ORIGINS)]
    # stage-2 rule: quality targets (top10_share) are judged on target years <= QUALITY_MAIN_MAX_TARGET_YEAR
    quality = ev["target"].map(lambda t: S2_TARGETS.get(t, {}).get("quality", False))
    ev = ev[~(quality & (ev["year"] > QUALITY_MAIN_MAX_TARGET_YEAR))]
    m = ev.groupby(["panel", "scheme", "target", "model", "uni"]).agg(
        n=("err_g", "size"), MAE_growth=("err_g", "mean"), MAE_level=("err_level", "mean")).reset_index()
    naive = m[m["model"] == "naive"].set_index(["panel", "scheme", "target", "uni"])["MAE_level"]
    m["MASE_vs_naive"] = m["MAE_level"].to_numpy() / naive.reindex(
        m.set_index(["panel", "scheme", "target", "uni"]).index).to_numpy()
    return m


def _compare(m, b, rng):
    n = len(m)
    idx = rng.integers(0, n, size=(C.BOOTSTRAP_SAMPLES, n))
    mm, bb = m[idx].mean(axis=1), b[idx].mean(axis=1)
    a = (1 - C.SUCCESS_CI_LEVEL) / 2
    lo, hi = np.quantile(mm - bb, [a, 1 - a])
    glo, ghi = np.quantile(1 - mm / bb, [a, 1 - a])
    gain = 1 - m.mean() / b.mean()
    return {"gain": gain, "diff_ci_lo": lo, "diff_ci_hi": hi, "gain_ci_lo": glo, "gain_ci_hi": ghi,
            "unis_beating": int((m < b).sum()), "n_unis": n,
            "passes": bool(gain >= C.SUCCESS_MIN_RELATIVE_MAE_GAIN and hi < 0)}


def criteria(pu):
    rows = []
    for (panel, scheme, target), g in pu.groupby(["panel", "scheme", "target"]):
        wide = g.pivot(index="uni", columns="model", values="MAE_growth").dropna()
        for model in C.MODELS:
            for base in ("naive",) + BASELINES_C2:
                if model == base:
                    continue
                rng = np.random.default_rng(C.RANDOM_SEED)
                res = _compare(wide[model].to_numpy(), wide[base].to_numpy(), rng)
                rows.append({"panel": panel, "scheme": scheme, "target": target, "model": model, "baseline": base,
                             "primary": model == C.PRIMARY_MODEL[target], "MAE_model": wide[model].mean(),
                             "MAE_baseline": wide[base].mean(), **res})
    return pd.DataFrame(rows)


def verdicts(cr):
    p = cr[cr["primary"]]
    out = []
    for (panel, target), g in p.groupby(["panel", "target"]):
        c1 = g[g["baseline"] == "naive"].set_index("scheme")
        c2 = g[g["baseline"].isin(BASELINES_C2)]
        out.append({"panel": panel, "target": target, "primary": C.PRIMARY_MODEL[target],
                    "C1": bool(c1["passes"].all()),
                    "C1_gain_rolling": c1.at["rolling", "gain"], "C1_gain_louo": c1.at["louo", "gain"],
                    "C1_ci_rolling": f"[{c1.at['rolling', 'diff_ci_lo']:.4f}; {c1.at['rolling', 'diff_ci_hi']:.4f}]",
                    "C1_ci_louo": f"[{c1.at['louo', 'diff_ci_lo']:.4f}; {c1.at['louo', 'diff_ci_hi']:.4f}]",
                    "C2": bool(c2["passes"].all()),
                    **{f"C2_gain_{b}_{s}": c2[(c2["baseline"] == b) & (c2["scheme"] == s)]["gain"].iloc[0]
                       for b in BASELINES_C2 for s in C.SCHEMES},
                    "n_unis": int(c1["n_unis"].max())})
    return pd.DataFrame(out)


# ── conformal, SHAP, AITU ───────────────────────────────────────────────────────────────

def growth_series(panel: pd.DataFrame, target: str) -> dict:
    """Full growth series of each university (same transform as build_rows, without the lag requirement)."""
    spec = C.TARGETS[target]
    years = pd.Index(range(C.PANEL_YEARS[0], C.PANEL_YEARS[1] + 1), name="year")
    out = {}
    for uni, g in panel.groupby("uni"):
        gi = g.set_index("year")
        works = gi["works_count"].reindex(years)
        start = works[works >= SERIES_START_MIN_WORKS].index.min()
        if pd.isna(start):
            continue
        y = gi[target].reindex(years).where(years >= max(start, spec.get("min_year", start)))
        tr = np.log(y.where(y > 0)) if spec["kind"] == "count" else y
        out[uni] = tr.diff().dropna()
    return out


def _sigma(growths, uni, upto):
    """CONFORMAL: sd of the university's growth in years <= origin, >= 3 values (else NaN)."""
    g = growths.get(uni, pd.Series(dtype=float))
    g = g[g.index <= upto]
    return g.std(ddof=1) if len(g) >= 3 else np.nan


def conformal(preds, panel_name="extended"):
    out = []
    for target, model in C.PRIMARY_MODEL.items():
        growths = growth_series(load(panel_name), target)
        p = preds[(preds["panel"] == panel_name) & (preds["target"] == target) & (preds["model"] == model)
                  & (preds["scheme"] == "rolling")].copy()
        p["sigma"] = [_sigma(growths, u, o) for u, o in zip(p["uni"], p["origin"])]
        floor = np.nanpercentile(p["sigma"], 5)
        p["sigma_missing"] = p["sigma"].isna()      # < 3 growth values: panel median (decision, see report)
        p["sigma"] = p["sigma"].fillna(p["sigma"].median()).clip(lower=floor)
        p["score"] = np.abs(p["g"] - p["g_pred"]) / p["sigma"]
        for origin in C.EVAL_ORIGINS:
            cal = p[p["year"] <= origin]["score"].to_numpy()
            test = p[p["origin"] == origin].copy()
            if len(cal) < 20 or test.empty:
                continue
            q = np.quantile(cal, min(1.0, np.ceil((len(cal) + 1) * 0.8) / len(cal)), method="higher")
            test["covered"] = np.abs(test["g"] - test["g_pred"]) <= q * test["sigma"]
            test["q"], test["floor"] = q, floor
            out.append(test.assign(target=target))
    c = pd.concat(out)
    terc = pd.qcut(c.groupby("uni")["size"].first(), 3, labels=["small", "medium", "large"])
    c["size_tercile"] = c["uni"].map(terc)
    cov = pd.concat([c.groupby("target")["covered"].mean().rename("all").to_frame(),
                     c.groupby(["target", "size_tercile"], observed=True)["covered"].mean().unstack()], axis=1)
    return c, cov


def shap_primary(panel_name="extended"):
    rows_out = []
    for target, model in C.PRIMARY_MODEL.items():
        rows = build_rows(load(panel_name), target)
        cols = features(target, rows)
        train = rows[rows["year"] <= max(C.EVAL_ORIGINS) + 1]
        params = tune(model, train, cols)
        est = _est(model, params).fit(train[cols], train["g"])
        if model == "lgbm":
            contrib = est.booster_.predict(train[cols], pred_contrib=True)[:, :-1]
            imp = np.abs(contrib).mean(axis=0)
            method = "TreeSHAP"
        else:
            coef = est.named_steps["ridge"].coef_
            imp = np.abs(coef)
            method = "|standardized coefficient| (linear model)"
        rows_out += [{"target": target, "model": model, "method": method, "feature": f, "importance": float(v)}
                     for f, v in zip(cols, imp)]
    return pd.DataFrame(rows_out)


def aitu(verdict, cov_q):
    """Forecast 2026 for AITU (external: fails the series rule) only for targets passing C1 on the extended panel."""
    full = pd.read_parquet(PANEL3_PATH)
    ext = full[full["role"] == "main"]
    a = full[full["uni"] == "AITU"]
    out = []
    v = verdict[verdict["panel"] == "extended"].set_index("target")
    for target, model in C.PRIMARY_MODEL.items():
        if not bool(v.at[target, "C1"]):
            out.append({"target": target, "status": "прогноз не строится: критерий C1 не пройден"})
            continue
        rows = build_rows(pd.concat([ext, a]), target)
        cols = features(target, rows)
        train = rows[(rows["uni"] != "AITU")]
        params = tune(model, train, cols)
        est = _est(model, params).fit(train[cols], train["g"])
        last = int(a["year"].max())
        ar = rows[(rows["uni"] == "AITU") & (rows["year"] == last)]
        if ar.empty:
            out.append({"target": target, "status": "прогноз не строится: у AITU нет полного набора признаков"})
            continue
        # features of year `last` predict the change last -> last+1: shift the row one step forward
        nxt = ar.copy()
        nxt["g_lag3"], nxt["g_lag2"], nxt["g_lag1"] = ar["g_lag2"], ar["g_lag1"], ar["g"]
        nxt["drift3"] = nxt[["g_lag1", "g_lag2", "g_lag3"]].mean(axis=1)
        is_count = C.TARGETS[target]["kind"] == "count"
        nxt["level_lag1"] = np.log(ar["y"]) if is_count else ar["y"]
        w = a.set_index("year")["works_count"]
        au = a.set_index("year")["unique_authors"]
        nxt["log_works_lag1"] = np.log(w[last])
        nxt["works_g_lag1"] = np.log(w[last] / w[last - 1])
        nxt["authors_g_lag1"] = np.log(au[last] / au[last - 1])
        nxt["age"] = ar["age"] + 1
        g = float(est.predict(nxt[cols])[0])
        sig = max(_sigma(growth_series(a, target), "AITU", last), cov_q.get(f"{target}__floor", 0))
        q = float(cov_q.get(target, np.nan))
        y = float(ar["y"].iloc[0])
        f = (lambda d: y * np.exp(d)) if is_count else (lambda d: min(max(y + d, 0), 1))
        out.append({"target": target, "status": "прогноз", "year": last + 1, "last_value": y, "forecast": f(g),
                    "lower80": f(g - q * sig), "upper80": f(g + q * sig), "model": model})
    return pd.DataFrame(out)


def aitu_percentiles():
    full = pd.read_parquet(PANEL3_PATH)
    y = full[(full["year"] == C.PANEL_YEARS[1]) & full["role"].isin(["main", "external"])].copy()
    y["citations_per_author"] = y["citations_received_in_year"] / y["unique_authors"].replace(0, np.nan)
    rows = []
    for col, label in (("works_count", "публикации"), ("citations_per_author", "цитирования на автора"),
                       ("intl_collab_share", "доля международных соавторств"),
                       ("n_partner_countries", "число стран-партнёров")):
        peers = y[y["role"] == "main"][col].dropna()
        v = float(y.loc[y["uni"] == "AITU", col].iloc[0])
        rows.append({"metric": col, "label": label, "year": C.PANEL_YEARS[1], "aitu": v,
                     "percentile": float((peers < v).mean() * 100 + (peers == v).mean() * 50),
                     "panel_median": float(peers.median()), "panel_n": len(peers)})
    return pd.DataFrame(rows)


def report():
    preds = pd.read_parquet(OUT / "predictions.parquet")
    pu = per_uni(preds)
    pu.to_csv(OUT / "metrics_per_uni.csv", index=False)
    cr = criteria(pu)
    cr.to_csv(OUT / "criteria_all_models.csv", index=False)
    v = verdicts(cr)
    v.to_csv(OUT / "verdicts.csv", index=False)
    c, cov = conformal(preds)
    cov.to_csv(OUT / "conformal_coverage.csv")
    last = c[c["origin"] == max(C.EVAL_ORIGINS)].groupby("target")
    q_last = {**last["q"].first().to_dict(), **{f"{t}__floor": v for t, v in last["floor"].first().items()}}
    c.groupby("target")["sigma_missing"].mean().to_csv(OUT / "conformal_sigma_fallback_share.csv")
    shap_primary().to_csv(OUT / "shap_importance.csv", index=False)
    aitu(v, q_last).to_csv(OUT / "aitu_forecast.csv", index=False)
    aitu_percentiles().to_csv(OUT / "aitu_percentiles.csv", index=False)
    pd.set_option("display.width", 250)
    print(v.round(3).to_string(index=False))
    print(cov.round(3))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["run", "report"])
    a = ap.parse_args()
    {"run": run, "report": report}[a.step]()


if __name__ == "__main__":
    main()
