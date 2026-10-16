"""Finance stage 4: budget structure -> outcomes. Descriptive associations, not effects.

Specification, hypotheses, sensitivities, placebo and the Holm correction are fixed in
src/finance/criterion_stage2.py (committed before this module was run).

  python -m src.finance.budget_outcomes
"""
import numpy as np
import pandas as pd
from scipy import stats

from src.finance import criterion_stage2 as C
from src.finance.baseline import _series
from src.finance.config import FINANCE_RESULTS_DIR
from src.finance.features_stage2 import add_lags, add_window_mean
from src.finance.panel import CATEGORIES
from src.finance.panel_stage2 import PANEL2_PATH

OUT_DIR = FINANCE_RESULTS_DIR / "stage2"
OPS = [c for c in CATEGORIES if c != "scholarships"]
COVID_YEARS = (2020, 2021, 2022)


# ── two-way FE with clustered SE ────────────────────────────────────────────────────────

def demean_two_way(df: pd.DataFrame, cols: list[str], unit: str, time: str, tol=1e-12, max_iter=10000):
    """Alternating projections: removes unit and time means (unbalanced panels)."""
    out = df[cols].astype(float).copy()
    for _ in range(max_iter):
        before = out.to_numpy().copy()
        out -= out.groupby(df[unit]).transform("mean")
        out -= out.groupby(df[time]).transform("mean")
        if np.max(np.abs(out.to_numpy() - before)) < tol:
            break
    return out


def drop_singletons(df: pd.DataFrame, unit: str) -> pd.DataFrame:
    while True:
        n = df.groupby(unit)[unit].transform("size")
        if (n > 1).all():
            return df
        df = df[n > 1]


def fe_ols(df: pd.DataFrame, y: str, xs: list[str], unit="series_id", time="year", cluster="series_id") -> dict:
    d = drop_singletons(df.dropna(subset=[y] + xs), unit).reset_index(drop=True)
    dm = demean_two_way(d, [y] + xs, unit, time)
    X, Y = dm[xs].to_numpy(), dm[y].to_numpy()
    bread = np.linalg.inv(X.T @ X)
    beta = bread @ X.T @ Y
    u = Y - X @ beta
    groups = d[cluster].to_numpy()
    meat = np.zeros((len(xs), len(xs)))
    for g in np.unique(groups):
        idx = groups == g
        s = X[idx].T @ u[idx]
        meat += np.outer(s, s)
    n, g_count = len(d), len(np.unique(groups))
    k = len(xs) + d[time].nunique() - 1  # unit FE are nested in clusters and not counted (as reghdfe)
    scale = g_count / (g_count - 1) * (n - 1) / (n - k)
    vcov = scale * bread @ meat @ bread
    se = np.sqrt(np.diag(vcov))
    t = beta / se
    p = 2 * stats.t.sf(np.abs(t), df=g_count - 1)
    crit = stats.t.ppf(0.975, df=g_count - 1)
    return {"beta": beta[0], "se": se[0], "ci_lo": beta[0] - crit * se[0], "ci_hi": beta[0] + crit * se[0],
            "p": p[0], "n_obs": n, "n_series": g_count, "years": f"{d[time].min()}-{d[time].max()}",
            "unscaled_vcov": bread @ meat @ bread}


def holm(pvals: list[float]) -> list[float]:
    order = np.argsort(pvals)
    m = len(pvals)
    adj, running = np.empty(m), 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvals[i]))
        adj[i] = running
    return adj.tolist()


# ── data ────────────────────────────────────────────────────────────────────────────────

def share_frame(panel: pd.DataFrame) -> pd.DataFrame:
    p = panel[~panel["superseded"]]
    f = p[["series_id", "year", "control", "id_transition", "merger_absorption"]].copy()
    ops_total = p[[f"exp_{c}" for c in OPS]].sum(axis=1, min_count=len(OPS))
    ops_total = ops_total.where(ops_total > 0)
    for c in OPS:
        f[f"{c}_share"] = 100 * p[f"exp_{c}"] / ops_total
    f["log_fte"] = np.log(p["fte_total"].where(p["fte_total"] > 0))
    f["log_core_real"] = np.log(p["core_total_per_fte_real"].where(p["core_total_per_fte_real"] > 0))
    return f


def hypothesis_frame(panel: pd.DataFrame, shares: pd.DataFrame, hyp: dict) -> pd.DataFrame:
    """Rows (series, outcome year t) with d_y, d_x (t), d_x_lag1 (t-1), d_x_lead1 (t+1), controls."""
    out = _series(panel, hyp["outcome"])[["series_id", "year", "change", "control"]].rename(columns={"change": "d_y"})
    col = f"{hyp['share']}_share"
    s = shares[["series_id", "year", col, "log_fte", "log_core_real", "id_transition", "merger_absorption"]].copy()
    if hyp["window"] == "cohort_t-5_t":
        s["x"] = add_window_mean(s, col, start=5, end=0)
    else:
        s["x"] = s[col]
    broken = s["id_transition"] | s["merger_absorption"]
    s = add_lags(s, ["x", "log_fte", "log_core_real"], lags=(1,))
    s["d_x"] = (s["x"] - s["x_lag1"]).where(~broken)
    s["d_log_fte"] = (s["log_fte"] - s["log_fte_lag1"]).where(~broken)
    s["d_log_core_real"] = (s["log_core_real"] - s["log_core_real_lag1"]).where(~broken)
    s = add_lags(s, ["d_x"], lags=(1,))
    lead = s[["series_id", "year", "d_x"]].assign(year=lambda d: d["year"] - 1).rename(columns={"d_x": "d_x_lead1"})
    s = s.merge(lead, on=["series_id", "year"], how="left")
    keep = ["series_id", "year", "d_x", "d_x_lag1", "d_x_lead1", "d_log_fte", "d_log_core_real"]
    return out.merge(s[keep], on=["series_id", "year"], how="inner")


def winsorize(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    d = df.copy()
    for c in cols:
        lo, hi = d[c].quantile([0.01, 0.99])
        d[c] = d[c].clip(lo, hi)
    return d


def estimate(frame: pd.DataFrame, x: str, spec: str) -> dict:
    d = frame.dropna(subset=["d_y", x])
    controls = []
    if spec == "no_covid":
        d = d[~d["year"].isin(COVID_YEARS)]
    if spec == "public_only":
        d = d[d["control"] == 1]
    if spec == "private_only":
        d = d[d["control"] == 2]
    if spec == "with_controls":
        controls = ["d_log_fte", "d_log_core_real"]
        d = d.dropna(subset=controls)
    if spec != "no_winsorize":
        d = winsorize(d, ["d_y", x] + controls)
    res = fe_ols(d, "d_y", [x] + controls)
    res.pop("unscaled_vcov")
    return res


def main():
    panel = pd.read_parquet(PANEL2_PATH)
    shares = share_frame(panel)
    rows = []
    for name, hyp in C.HYPOTHESES.items():
        frame = hypothesis_frame(panel, shares, hyp)
        specs = [("main", "d_x", "main")] + [(k, "d_x_lag1" if k == "lag1" else "d_x", k) for k in C.SENSITIVITY]
        specs.append(("placebo_lead", "d_x_lead1", "main"))
        for spec, x, how in specs:
            rows.append({"hypothesis": name, "outcome": hyp["outcome"], "share": hyp["share"],
                         "window": hyp["window"], "expected_sign": hyp["expected_sign"], "spec": spec,
                         **estimate(frame, x, how)})
        print(name, "done", flush=True)
    res = pd.DataFrame(rows)
    res["p_holm"] = np.nan
    for spec, idx in res.groupby("spec").groups.items():
        res.loc[idx, "p_holm"] = holm(res.loc[idx, "p"].tolist())

    def verdict(r):
        if r["spec"] == "placebo_lead":
            return "lead significant (confounding/reverse causation sign)" if r["p"] < C.ALPHA else "lead not significant"
        same = np.sign(r["beta"]) == r["expected_sign"]
        if r["spec"] != "main":  # sensitivity: descriptive only, the pre-registered verdict is the main spec
            sign = "sign as expected" if same else "sign opposite"
            return (f"raw p {'<' if r['p'] < C.ALPHA else '>='} 0.05, Holm in family "
                    f"{'<' if r['p_holm'] < C.ALPHA else '>='} 0.05, {sign}")
        if r["p_holm"] >= C.ALPHA:
            return "no association detected"
        return "association supported" if same else "association in the opposite direction"
    res["verdict"] = res.apply(verdict, axis=1)
    res.to_csv(OUT_DIR / "hypotheses.csv", index=False)
    pd.set_option("display.width", 250)
    print(res[["hypothesis", "spec", "beta", "ci_lo", "ci_hi", "p", "p_holm", "n_obs", "n_series", "years",
               "verdict"]].round(4).to_string(index=False))


if __name__ == "__main__":
    main()
