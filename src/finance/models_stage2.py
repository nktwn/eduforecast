"""Finance stage 3: forecasting models evaluated against the pre-registered F1 criterion.

Design: src/finance/criterion_stage2.py (committed before this module was run).

  python -m src.finance.models_stage2 rolling      # rolling origin 2014-2022 + intervals
  python -m src.finance.models_stage2 unseen       # institutions the model has not seen
  python -m src.finance.models_stage2 explain      # SHAP / coefficients at origin 2022
  python -m src.finance.models_stage2 report       # criterion tables from saved predictions
  python -m src.finance.models_stage2 deploy       # primary model on all years <= 2023 for the app
"""
import argparse
import itertools
import json

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

from src.finance import criterion_stage2 as C
from src.finance.baseline import _series, bootstrap_gain, predictions as baseline_predictions
from src.finance.config import FINANCE_DATA_DIR, FINANCE_RESULTS_DIR
from src.finance.features_stage2 import add_lags
from src.finance.panel import CATEGORIES
from src.finance.panel_stage2 import PANEL2_PATH

OUT_DIR = FINANCE_RESULTS_DIR / "stage2"
MODEL_DIR = FINANCE_DATA_DIR / "models" / "stage2"
OUT_DIR.mkdir(parents=True, exist_ok=True)
MODEL_DIR.mkdir(parents=True, exist_ok=True)

OPS = [c for c in CATEGORIES if c != "scholarships"]
CARNEGIE_CODES = {g: i for i, g in enumerate(["R1", "R2", "D/PU", "Master's L", "Master's M", "Master's S",
                                               "Baccalaureate", "Special focus", "Tribal", "Other",
                                               "Unclassified"])}
COMBOS = [("constant", None)] + [(m, s) for m in ("ridge", "lgbm") for s in ("S1", "S2", "S3")]


def _log(s):
    return np.log(s.where(s > 0))


# ── features ────────────────────────────────────────────────────────────────────────────

def common_features(panel: pd.DataFrame) -> pd.DataFrame:
    """Non-target features per (series_id, year), all from year t only (lags explicit)."""
    p = panel[~panel["superseded"]].copy()
    f = p[["series_id", "year", "unitid", "name", "control", "control_label", "carnegie_group", "peer_group"]].copy()
    f["log_fte"] = _log(p["fte_total"])
    f["log_enrollment"] = _log(p["fall_enrollment"])
    f["control_public"] = (p["control"] == 1).astype(float)
    f["carnegie"] = p["carnegie_group"].map(CARNEGIE_CODES).astype(float)
    ops_total = p[[f"exp_{c}" for c in OPS]].sum(axis=1, min_count=len(OPS))
    ops_total = ops_total.where(ops_total > 0)
    for c in OPS:
        f[f"{c}_share_ops"] = p[f"exp_{c}"] / ops_total
    f["log_core_real"] = _log(p["core_total_per_fte_real"])
    for c in ("instruction", "student_services", "academic_support", "institutional_support"):
        f[f"log_{c}_real"] = _log(p[f"{c}_per_fte_real"])
    for c in ("nat_compensation_share", "nat_depreciation_share", "nat_interest_share", "admit_rate", "yield_rate",
              "pell_share_ug", "inst_aid_share_ftft", "ft_instr_staff_share", "fte_per_faculty",
              "full_time_share", "graduate_share", "deg_share_stem", "deg_share_computer_science",
              "deg_share_engineering", "deg_share_health", "deg_share_business", "deg_share_education",
              "deg_share_humanities_arts", "deg_share_social_behavioral"):
        f[c] = p[c]
    f["sch_gross_share"] = p["sch_gross_share_of_total_with_discounts"]
    f["log_net_price_real"] = _log(p["net_price_real"])
    f["log_tuition_instate_real"] = _log(p["tuition_fees_instate_real"])
    f["log_faculty_salary_real"] = _log(p["faculty_avg_salary_9mo_real"])
    f["broken"] = p["id_transition"] | p["merger_absorption"]
    f = add_lags(f, [f"{c}_share_ops" for c in OPS] + ["log_core_real"], lags=(1, 2))
    f["core_real_growth_1"] = (f["log_core_real"] - f["log_core_real_lag1"]).where(~f["broken"])
    f["core_real_growth_2"] = add_lags(f[["series_id", "year", "core_real_growth_1"]], ["core_real_growth_1"],
                                       lags=(1,))["core_real_growth_1_lag1"].to_numpy()
    return f


def target_frame(panel: pd.DataFrame, common: pd.DataFrame, target: str) -> pd.DataFrame:
    """Rows = (series, year t) with features of year t and label = change t -> t+1 (target_year = t+1)."""
    s = _series(panel, target)[["series_id", "year", "z", "change"]]
    s = add_lags(s, ["change"], lags=(1, 2))
    s = s.rename(columns={"z": "target_level", "change": "target_change_1", "change_lag1": "target_change_2",
                          "change_lag2": "target_change_3"})
    nxt = _series(panel, target)[["series_id", "year", "change"]].assign(year=lambda d: d["year"] - 1)
    s = s.merge(nxt.rename(columns={"change": "y_next"}), on=["series_id", "year"], how="left")
    f = common.merge(s, on=["series_id", "year"], how="inner")
    f["target_year"] = f["year"] + 1
    return f


# ── models ──────────────────────────────────────────────────────────────────────────────

class RidgeModel:
    def __init__(self, features, alpha):
        self.features, self.alpha = features, alpha

    def _matrix(self, X: pd.DataFrame) -> pd.DataFrame:
        cols = [c for c in self.features if c != "carnegie"]
        m = X[cols].astype(float).clip(self.lo, self.hi, axis=1).fillna(self.med)
        m = (m - self.mu) / self.sd
        if "carnegie" in self.features:
            for code in range(len(CARNEGIE_CODES)):
                m[f"carnegie_{code}"] = (X["carnegie"] == code).astype(float)
        return m

    def fit(self, X, y):
        cols = [c for c in self.features if c != "carnegie"]
        Z = X[cols].astype(float)
        self.lo, self.hi = Z.quantile(0.01), Z.quantile(0.99)
        Z = Z.clip(self.lo, self.hi, axis=1)
        self.med = Z.median().fillna(0.0)  # a feature with no training values becomes a constant 0
        Z = Z.fillna(self.med)
        self.mu, self.sd = Z.mean(), Z.std().replace(0, 1).fillna(1)
        self.model = Ridge(alpha=self.alpha).fit(self._matrix(X), y)
        return self

    def predict(self, X):
        return self.model.predict(self._matrix(X))

    def coefficients(self) -> pd.Series:
        return pd.Series(self.model.coef_, index=self.model.feature_names_in_)


class ConstantModel:
    def fit(self, X, y):
        self.c = float(np.mean(y))
        return self

    def predict(self, X):
        return np.full(len(X), self.c)


def make(kind, features, params):
    if kind == "constant":
        return ConstantModel()
    if kind == "ridge":
        return RidgeModel(features, params["alpha"])
    return lgb.LGBMRegressor(**C.LGBM_FIXED, **params)


def grid(kind):
    if kind == "constant":
        return [{}]
    if kind == "ridge":
        return [{"alpha": a} for a in C.RIDGE_ALPHAS]
    keys = list(C.LGBM_GRID)
    return [dict(zip(keys, v)) for v in itertools.product(*C.LGBM_GRID.values())]


def _fit(model, X, y, features):
    if isinstance(model, lgb.LGBMRegressor):
        return model.fit(X[features], y)
    return model.fit(X, y)


def _predict(model, X, features):
    if isinstance(model, lgb.LGBMRegressor):
        return model.predict(X[features])
    return model.predict(X)


def fit_selected(train: pd.DataFrame, kind: str, set_name: str | None, origin: int):
    """Nested selection: candidates fit on target years <= origin-1, scored on origin; refit on <= origin."""
    features = C.FEATURE_SETS[set_name] if set_name else []
    rows = train[train["target_year"] <= origin]
    candidates = grid(kind)
    best = candidates[0]
    if len(candidates) > 1:
        inner, val = rows[rows["target_year"] <= origin - 1], rows[rows["target_year"] == origin]
        scores = []
        for params in candidates:
            m = _fit(make(kind, features, params), inner, inner["y_next"].to_numpy(), features)
            scores.append(np.mean(np.abs(_predict(m, val, features) - val["y_next"].to_numpy())))
        best = candidates[int(np.argmin(scores))]
    model = _fit(make(kind, features, best), rows, rows["y_next"].to_numpy(), features)
    return model, best, features


# ── evaluation ──────────────────────────────────────────────────────────────────────────

def size_terciles(panel: pd.DataFrame) -> pd.Series:
    med = _log(panel.loc[~panel["superseded"], "fte_total"]).groupby(panel["series_id"]).median()
    return pd.qcut(med, 3, labels=["small", "medium", "large"])


def _sigma(frame: pd.DataFrame, max_year: int) -> pd.Series:
    """Std of each series' target changes in years <= max_year (>= 3 changes)."""
    ch = frame.loc[frame["year"] <= max_year, ["series_id", "target_change_1"]].dropna()
    g = ch.groupby("series_id")["target_change_1"]
    return g.std().where(g.size() >= 3)


def rolling(panel: pd.DataFrame) -> None:
    common = common_features(panel)
    all_preds, chosen, calib = [], [], []
    for target in C.TARGET_LIST:
        frame = target_frame(panel, common, target)
        train_rows = frame.dropna(subset=["y_next", "target_level"])
        points = baseline_predictions(panel, target)[["series_id", "year", "z", "z_prev", "err_naive", "flagged",
                                                      "control", "peer_group"]]
        test = points.rename(columns={"year": "target_year"}).merge(
            frame.drop(columns=["control", "peer_group"]), on=["series_id", "target_year"], how="left",
            validate="one_to_one")
        assert np.allclose(test["target_level"], test["z_prev"]), target
        for kind, set_name in COMBOS:
            label = kind if set_name is None else f"{kind}_{set_name}"
            prev_model = None
            for origin in range(min(C.EVAL_ORIGINS) - 1, max(C.EVAL_ORIGINS) + 1):
                model, params, features = fit_selected(train_rows, kind, set_name, origin)
                chosen.append({"target": target, "model": label, "origin": origin, **params})
                if (kind, set_name) == C.PRIMARY:
                    # calibration rows for origin `origin`: the origin-1 model on target year `origin`
                    if prev_model is not None:
                        cal = train_rows[train_rows["target_year"] == origin].copy()
                        cal["pred"] = _predict(prev_model, cal, features)
                        cal["origin"] = origin
                        cal["sigma"] = cal["series_id"].map(_sigma(frame, origin - 1))
                        calib.append(cal[["series_id", "target_year", "origin", "y_next", "pred", "sigma"]]
                                     .assign(target=target))
                    prev_model = model
                if origin not in C.EVAL_ORIGINS:
                    continue
                t = test[test["target_year"] == origin + 1]
                pred = _predict(model, t, features)
                all_preds.append(pd.DataFrame({
                    "target": target, "model": label, "origin": origin, "series_id": t["series_id"].to_numpy(),
                    "target_year": t["target_year"].to_numpy(), "z": t["z"].to_numpy(),
                    "z_prev": t["z_prev"].to_numpy(), "forecast": t["z_prev"].to_numpy() + pred,
                    "err_naive": t["err_naive"].to_numpy(), "flagged": t["flagged"].to_numpy(),
                    "sigma": t["series_id"].map(_sigma(frame, origin)).to_numpy()}))
            print(target, label, "done", flush=True)
    preds = pd.concat(all_preds, ignore_index=True)
    preds["err_model"] = (preds["forecast"] - preds["z"]).abs()
    preds.to_parquet(OUT_DIR / "rolling_predictions.parquet", index=False)
    pd.DataFrame(chosen).to_csv(OUT_DIR / "chosen_hyperparameters.csv", index=False)
    pd.concat(calib, ignore_index=True).to_parquet(OUT_DIR / "calibration_rows.parquet", index=False)


def criterion_table(preds: pd.DataFrame, group_cols=("target", "model")) -> pd.DataFrame:
    rows = []
    for key, p in preds.groupby(list(group_cols)):
        for scope in C.EVAL_SCOPES:
            q = p if scope == "all_years" else p[~p["flagged"]]
            per = q.groupby("series_id")[["err_model", "err_naive"]].mean()
            res = bootstrap_gain(per, "model", np.random.default_rng(C.RANDOM_SEED))
            rows.append({**dict(zip(group_cols, key if isinstance(key, tuple) else (key,))), "scope": scope,
                         "n_points": len(q), **res})
    return pd.DataFrame(rows)


def breakdown(preds: pd.DataFrame, panel: pd.DataFrame) -> pd.DataFrame:
    info = panel[~panel["superseded"]].sort_values("year").groupby("series_id")[
        ["control_label", "carnegie_group"]].last()
    info["size_tercile"] = size_terciles(panel)
    p = preds.join(info, on="series_id")
    rows = []
    for col in C.BREAKDOWNS:
        for (target, model, grp), q in p.groupby(["target", "model", col], observed=True):
            per = q.groupby("series_id")[["err_model", "err_naive"]].mean()
            rows.append({"target": target, "model": model, "breakdown": col, "group": grp,
                         "n_series": len(per), "MAE_naive": per["err_naive"].mean(),
                         "MAE_model": per["err_model"].mean(),
                         "gain_vs_naive": 1 - per["err_model"].mean() / per["err_naive"].mean(),
                         "series_beating_naive": int((per["err_model"] < per["err_naive"]).sum())})
    return pd.DataFrame(rows)


def intervals(preds: pd.DataFrame, calib: pd.DataFrame, panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    label = f"{C.PRIMARY[0]}_{C.PRIMARY[1]}"
    p = preds[preds["model"] == label].copy()
    out = []
    for (target, origin), q in p.groupby(["target", "origin"]):
        cal = calib[(calib["target"] == target) & (calib["origin"] == origin)].copy()
        floor = cal["sigma"].quantile(0.05)
        cal["sigma"] = cal["sigma"].fillna(cal["sigma"].median()).clip(lower=floor)
        s = np.abs(cal["y_next"] - cal["pred"]) / cal["sigma"]
        n = len(s)
        qhat = float(np.quantile(s, min(1.0, np.ceil((n + 1) * C.INTERVAL_LEVEL) / n), method="higher"))
        sig = q["sigma"].fillna(cal["sigma"].median()).clip(lower=floor)
        q = q.assign(lower=q["forecast"] - qhat * sig, upper=q["forecast"] + qhat * sig, qhat=qhat)
        out.append(q)
    p = pd.concat(out)
    p["covered"] = (p["z"] >= p["lower"]) & (p["z"] <= p["upper"])
    p["width"] = p["upper"] - p["lower"]
    info = panel[~panel["superseded"]].sort_values("year").groupby("series_id")[["control_label"]].last()
    info["size_tercile"] = size_terciles(panel)
    p = p.join(info, on="series_id")
    p["covid_target_year"] = p["target_year"].isin([2020, 2021, 2022])
    rows = []
    for col in (None, "control_label", "size_tercile", "covid_target_year"):
        groups = p.groupby(["target"] + ([col] if col else []), observed=True)
        for key, q in groups:
            key = key if isinstance(key, tuple) else (key,)
            rows.append({"target": key[0], "breakdown": col or "all", "group": key[1] if col else "all",
                         "n": len(q), "coverage": q["covered"].mean(), "median_width": q["width"].median()})
    return p, pd.DataFrame(rows)


# ── unseen institutions ─────────────────────────────────────────────────────────────────

def unseen(panel: pd.DataFrame) -> None:
    common = common_features(panel)
    rows = []
    for target in C.TARGET_LIST:
        frame = target_frame(panel, common, target)
        train_rows = frame.dropna(subset=["y_next", "target_level"])
        points = baseline_predictions(panel, target)[["series_id", "year", "z", "z_prev", "err_naive", "flagged"]]
        test = points.rename(columns={"year": "target_year"}).merge(frame, on=["series_id", "target_year"],
                                                                    how="left", validate="one_to_one")
        series = np.sort(test["series_id"].unique())
        for split, seed in enumerate(C.UNSEEN["split_seeds"]):
            rng = np.random.default_rng(seed)
            held = set(rng.choice(series, size=int(round(C.UNSEEN["holdout_share"] * len(series))), replace=False))
            tr = train_rows[~train_rows["series_id"].isin(held)]
            for origin in C.UNSEEN["origins"]:
                t = test[(test["target_year"] == origin + 1) & test["series_id"].isin(held)]
                for kind, set_name in COMBOS:
                    model, _, features = fit_selected(tr, kind, set_name, origin)
                    pred = _predict(model, t, features)
                    rows.append(pd.DataFrame({
                        "target": target, "model": kind if set_name is None else f"{kind}_{set_name}",
                        "split": split, "origin": origin, "series_id": t["series_id"].to_numpy(),
                        "target_year": t["target_year"].to_numpy(), "flagged": t["flagged"].to_numpy(),
                        "err_naive": t["err_naive"].to_numpy(),
                        "err_model": np.abs(t["z_prev"].to_numpy() + pred - t["z"].to_numpy())}))
            print(target, "split", split, "done", flush=True)
    pd.concat(rows, ignore_index=True).to_parquet(OUT_DIR / "unseen_predictions.parquet", index=False)


# ── explainability ──────────────────────────────────────────────────────────────────────

def explain(panel: pd.DataFrame) -> None:
    common = common_features(panel)
    origin = max(C.EVAL_ORIGINS)
    imp, coefs, meta = [], [], {"origin": origin, "targets": {}}
    for target in C.TARGET_LIST:
        frame = target_frame(panel, common, target)
        train_rows = frame.dropna(subset=["y_next", "target_level"])
        model, params, features = fit_selected(train_rows, *C.PRIMARY, origin)
        model.booster_.save_model(str(MODEL_DIR / f"lgbm_S3_{target}.txt"))
        X = train_rows[train_rows["target_year"] <= origin][features]
        contrib = model.booster_.predict(X, pred_contrib=True)
        imp.append(pd.DataFrame({"target": target, "feature": features,
                                 "mean_abs_shap": np.abs(contrib[:, :-1]).mean(axis=0)}))
        ridge, rparams, rfeat = fit_selected(train_rows, "ridge", "S3", origin)
        coefs.append(ridge.coefficients().rename("std_coef").reset_index().rename(columns={"index": "feature"})
                     .assign(target=target, alpha=rparams["alpha"]))
        meta["targets"][target] = {"params": params, "fit_rows": int(len(X)), "ridge_alpha": rparams["alpha"]}
    pd.concat(imp).to_csv(OUT_DIR / "shap_importance.csv", index=False)
    pd.concat(coefs).to_csv(OUT_DIR / "ridge_coefficients.csv", index=False)
    (MODEL_DIR / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


# ── deployment (same procedure, all target years <= 2023) ──────────────────────────────

DEPLOY_ORIGIN = max(C.EVAL_ORIGINS) + 1  # 2023: last observed target year; forecasts are for 2024


def deploy(panel: pd.DataFrame) -> None:
    """Primary model refitted by the evaluated procedure on target years <= 2023, plus its interval.

    Calibration as in the evaluation: the origin-2022 model on target year 2023, scores normalized
    by the series' volatility of changes up to 2022.
    """
    common = common_features(panel)
    crit_path = OUT_DIR / "criterion_rolling.csv"
    crit = pd.read_csv(crit_path) if crit_path.exists() else None
    label = f"{C.PRIMARY[0]}_{C.PRIMARY[1]}"
    meta = {"version": "stage2-lgbm-S3-1.0", "trained_through_year": DEPLOY_ORIGIN, "interval_level": C.INTERVAL_LEVEL,
            "features": C.FEATURE_SETS[C.PRIMARY[1]], "targets": {}}
    for target in C.TARGET_LIST:
        frame = target_frame(panel, common, target)
        train_rows = frame.dropna(subset=["y_next", "target_level"])
        model, params, features = fit_selected(train_rows, *C.PRIMARY, DEPLOY_ORIGIN)
        model.booster_.save_model(str(MODEL_DIR / f"deploy_{target}.txt"))
        prev, _, _ = fit_selected(train_rows, *C.PRIMARY, DEPLOY_ORIGIN - 1)
        cal = train_rows[train_rows["target_year"] == DEPLOY_ORIGIN].copy()
        cal["sigma"] = cal["series_id"].map(_sigma(frame, DEPLOY_ORIGIN - 1))
        floor = float(cal["sigma"].quantile(0.05))
        med = float(cal["sigma"].median())
        sig = cal["sigma"].fillna(med).clip(lower=floor)
        sc = np.abs(cal["y_next"] - _predict(prev, cal, features)) / sig
        qhat = float(np.quantile(sc, min(1.0, np.ceil((len(sc) + 1) * C.INTERVAL_LEVEL) / len(sc)), method="higher"))
        status = None
        if crit is not None:
            c = crit[(crit["target"] == target) & (crit["model"] == label)].set_index("scope")
            status = {scope: {"meets_success_rule": bool(c.at[scope, "meets_success_rule"]),
                              "gain_vs_naive": float(c.at[scope, "gain_vs_naive"])} for scope in c.index}
        meta["targets"][target] = {"params": params, "qhat": qhat, "sigma_floor": floor, "sigma_median": med,
                                   "fit_rows": int((train_rows["target_year"] <= DEPLOY_ORIGIN).sum()),
                                   "criterion": status}
        print(target, meta["targets"][target], flush=True)
    (MODEL_DIR / "deploy_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")


# ── report ──────────────────────────────────────────────────────────────────────────────

def report(panel: pd.DataFrame) -> None:
    preds = pd.read_parquet(OUT_DIR / "rolling_predictions.parquet")
    calib = pd.read_parquet(OUT_DIR / "calibration_rows.parquet")
    table = criterion_table(preds)
    table.to_csv(OUT_DIR / "criterion_rolling.csv", index=False)
    breakdown(preds, panel).to_csv(OUT_DIR / "breakdown_rolling.csv", index=False)
    iv, cov = intervals(preds, calib, panel)
    cov.to_csv(OUT_DIR / "interval_coverage.csv", index=False)
    iv[["target", "origin", "series_id", "target_year", "forecast", "lower", "upper", "qhat", "covered"]].to_parquet(
        OUT_DIR / "intervals.parquet", index=False)
    pd.set_option("display.width", 250)
    print(table[["target", "model", "scope", "n_points", "n_institutions", "MAE_naive", "MAE_model",
                 "gain_vs_naive", "diff_ci_lo", "diff_ci_hi", "meets_success_rule"]].round(4).to_string(index=False))
    print(cov.round(3).to_string(index=False))
    up = OUT_DIR / "unseen_predictions.parquet"
    if up.exists():
        u = pd.read_parquet(up)
        ut = criterion_table(u, ("target", "model", "split"))
        ut.to_csv(OUT_DIR / "criterion_unseen.csv", index=False)
        summ = ut.groupby(["target", "model", "scope"]).agg(
            splits_passing=("meets_success_rule", "sum"), gain_mean=("gain_vs_naive", "mean"),
            gain_min=("gain_vs_naive", "min"), gain_max=("gain_vs_naive", "max")).reset_index()
        summ.to_csv(OUT_DIR / "criterion_unseen_summary.csv", index=False)
        print(summ.round(4).to_string(index=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["rolling", "unseen", "explain", "report", "deploy"])
    args = ap.parse_args()
    panel = pd.read_parquet(PANEL2_PATH)
    {"rolling": rolling, "unseen": unseen, "explain": explain, "report": report, "deploy": deploy}[args.step](panel)


if __name__ == "__main__":
    main()
