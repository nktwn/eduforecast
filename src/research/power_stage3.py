"""Stage 3 power analysis, computed BEFORE any stage-3 model from stage-2 saved metrics and the
existing works files (no new model, no new data).

For each target and scheme: per-university differences d_u = MAE_u(primary model) - MAE_u(naive) on the
growth scale from stage 2 (13 universities, main sample). With n universities:
  CI half-width   = 1.96 * sd(d_u) / sqrt(n)                      (normal approximation to the bootstrap)
  MDE (80% power) = (1.96 + 0.84) * sd(d_u) / sqrt(n) / mean_u MAE_u(naive)   (relative gain)
The criterion also needs a >= 10% gain, so the detectable gain is max(10%, MDE).
New international counts have no stage-2 model: their naive MAE comes from the saved works of the 13
universities, and sd(d_u) / mean MAE(naive) is assumed equal to that of works_count (stated assumption).
n_partner_institutions needs institution ids that the saved works do not hold: n_intl_works is its proxy.

  python -m src.research.power_stage3
"""
import numpy as np
import pandas as pd

from src.research.config import RESEARCH_RESULTS_DIR, WORKS_DIR
from src.research.stage2_config import STAGE2_DIR

OUT = RESEARCH_RESULTS_DIR / "stage3" / "power.csv"
PRIMARY = {"works_count": "lgbm", "unique_authors": "lgbm", "citations_received_in_year": "lgbm",
           "intl_collab_share": "ridge", "top10_share": "ridge"}
NS = (13, 40, 50, 60)
Z, Z80 = 1.96, 0.84
MAIN13 = ["NU", "KBTU", "SATBAYEV", "KAZNU", "ENU", "NARXOZ", "KIMEP", "SHAKARIM", "AITU", "SKOLTECH",
          "INNOPOLIS", "UNIST", "MBZUAI"]


def _row(target, scheme, sd, naive_mean, n_unis_obs, note=""):
    out = {"target": target, "scheme": scheme, "n_observed": n_unis_obs, "sd_diff": sd,
           "mean_mae_naive": naive_mean, "note": note}
    for n in NS:
        out[f"ci_halfwidth_n{n}"] = Z * sd / np.sqrt(n)
        mde = (Z + Z80) * sd / np.sqrt(n) / naive_mean
        out[f"mde80_rel_n{n}"] = mde
        out[f"detectable_gain_n{n}"] = max(0.10, mde)
    return out


def existing_targets() -> list[dict]:
    m = pd.read_csv(STAGE2_DIR / "metrics_per_uni.csv")
    m = m[(m["scenario"] == "main") & (m["subset"] == "main")]
    rows = []
    for target, model in PRIMARY.items():
        for scheme in ("rolling", "louo"):
            q = m[(m["target"] == target) & (m["scheme"] == scheme)]
            w = q.pivot_table(index="uni", columns="model", values="MAE_growth")
            d = (w[model] - w["naive"]).dropna()
            rows.append(_row(target, scheme, float(d.std(ddof=1)), float(w["naive"].mean()), len(d)))
    return rows


def intl_naive_mae() -> dict:
    """Naive MAE of log growth for the international counts, target years 2019-2025, 13 universities."""
    out = {}
    for name in ("n_partner_countries", "n_intl_works"):
        maes = []
        for uni in MAIN13:
            w = pd.read_parquet(WORKS_DIR / f"{uni}.parquet")
            w = w[(w["is_retracted"] != True) & (w["is_paratext"] != True) & w["year"].between(2010, 2025)]  # noqa: E712
            if name == "n_intl_works":
                s = w[w["n_countries"].fillna(0) >= 2].groupby("year").size()
            else:
                s = w.explode("countries").groupby("year")["countries"].nunique() - 1  # minus the home country
            s = s.reindex(range(2010, 2026)).fillna(0)
            g = np.log(s.where(s > 0)).diff().loc[2019:2025].dropna()
            if len(g) >= 3:
                maes.append(float(np.abs(g.diff().dropna()).mean()))  # naive growth = last year's growth
        out[name] = float(np.mean(maes))
    return out


def main():
    rows = existing_targets()
    ratio = {r["scheme"]: r["sd_diff"] / r["mean_mae_naive"] for r in rows if r["target"] == "works_count"}
    naive = intl_naive_mae()
    for target, base in (("n_partner_countries", "n_partner_countries"), ("n_intl_works", "n_intl_works"),
                         ("n_partner_institutions", "n_intl_works")):
        for scheme in ("rolling", "louo"):
            note = "assumed sd/MAE ratio of works_count" + ("; proxy: n_intl_works" if base != target else "")
            rows.append(_row(target, scheme, ratio[scheme] * naive[base], naive[base], 13, note))
    out = pd.DataFrame(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)
    pd.set_option("display.width", 250)
    cols = ["target", "scheme", "mean_mae_naive", "sd_diff"] + [f"mde80_rel_n{n}" for n in NS]
    print(out[cols].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
