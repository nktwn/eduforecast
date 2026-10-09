import numpy as np
import pandas as pd

from src.finance.config import FINANCE_RESULTS_DIR, PANEL_PATH
from src.finance.criterion import (
    BOOTSTRAP_SAMPLES,
    EVAL_ORIGINS,
    GROUP_COLUMN,
    GROUP_CHANGE_CLIP,
    GROUP_MIN_SIZE,
    RANDOM_SEED,
    SUCCESS_CI_LEVEL,
    SUCCESS_MIN_RELATIVE_MAE_GAIN,
    TARGETS,
)


def _series(panel: pd.DataFrame, target: str) -> pd.DataFrame:
    kind = TARGETS[target]["kind"]
    s = panel[["unitid", "year", GROUP_COLUMN, target]].copy()
    if kind == "log":
        s = s[s[target] > 0]
        s["z"] = np.log(s[target])
    else:
        s["z"] = s[target]
    s = s.dropna(subset=["z"]).sort_values(["unitid", "year"])
    full = s.set_index(["unitid", "year"])
    prev = full["z"].rename("z_prev")
    prev.index = prev.index.set_levels(prev.index.levels[1] + 1, level=1)
    s = s.join(prev, on=["unitid", "year"])
    s["change"] = s["z"] - s["z_prev"]
    return s


def predictions(panel: pd.DataFrame, target: str) -> pd.DataFrame:
    s = _series(panel, target)
    changes = s.dropna(subset=["change"]).copy()
    clip = GROUP_CHANGE_CLIP[TARGETS[target]["kind"]]
    changes["change_clipped"] = changes["change"].clip(-clip, clip)
    group = changes.groupby([GROUP_COLUMN, "year"])["change_clipped"].agg(["mean", "size"])
    group = group[group["size"] >= GROUP_MIN_SIZE]["mean"].rename("group_change")
    group.index = group.index.set_levels(group.index.levels[1] + 1, level=1)

    test = changes[changes["year"].isin([o + 1 for o in EVAL_ORIGINS])].join(group, on=[GROUP_COLUMN, "year"])
    test = test.dropna(subset=["group_change"])
    test["pred_naive"] = test["z_prev"]
    test["pred_group"] = test["z_prev"] + test["group_change"]
    test["err_naive"] = (test["pred_naive"] - test["z"]).abs()
    test["err_group"] = (test["pred_group"] - test["z"]).abs()
    test.insert(0, "target", target)
    return test


def bootstrap_gain(per_inst: pd.DataFrame, model: str, rng) -> dict:
    m, b = per_inst[f"err_{model}"].to_numpy(), per_inst["err_naive"].to_numpy()
    n = len(m)
    idx = rng.integers(0, n, size=(BOOTSTRAP_SAMPLES, n))
    mm, bb = m[idx].mean(axis=1), b[idx].mean(axis=1)
    alpha = (1 - SUCCESS_CI_LEVEL) / 2
    lo, hi = np.quantile(mm - bb, [alpha, 1 - alpha])
    gain = 1 - m.mean() / b.mean()
    return {"MAE_naive": b.mean(), f"MAE_{model}": m.mean(), "gain_vs_naive": gain,
            "diff_ci_lo": lo, "diff_ci_hi": hi, "ci_width_pct_of_naive": (hi - lo) / b.mean() * 100,
            "institutions_beating_naive": int((m < b).sum()), "n_institutions": n,
            "meets_success_rule": bool(gain >= SUCCESS_MIN_RELATIVE_MAE_GAIN and hi < 0)}


def main():
    panel = pd.read_parquet(PANEL_PATH)
    rng = np.random.default_rng(RANDOM_SEED)
    preds = pd.concat([predictions(panel, t) for t in TARGETS], ignore_index=True)
    preds.to_csv(FINANCE_RESULTS_DIR / "baseline_predictions.csv", index=False)

    summary, by_year, by_group = [], [], []
    for target, p in preds.groupby("target"):
        per_inst = p.groupby("unitid")[["err_naive", "err_group"]].mean()
        summary.append({"target": target, "unit": TARGETS[target]["unit"], "n_points": len(p),
                        **bootstrap_gain(per_inst, "group", rng)})
        y = p.groupby("year")[["err_naive", "err_group"]].mean().reset_index()
        by_year.append(y.assign(target=target, n=p.groupby("year").size().to_numpy()))
        g = p.groupby(GROUP_COLUMN)[["err_naive", "err_group"]].mean().reset_index()
        by_group.append(g.assign(target=target, n=p.groupby(GROUP_COLUMN).size().to_numpy()))

    pd.DataFrame(summary).to_csv(FINANCE_RESULTS_DIR / "baseline_summary.csv", index=False)
    pd.concat(by_year).to_csv(FINANCE_RESULTS_DIR / "baseline_by_year.csv", index=False)
    pd.concat(by_group).to_csv(FINANCE_RESULTS_DIR / "baseline_by_group.csv", index=False)
    print(pd.DataFrame(summary).round(4).to_string(index=False))


if __name__ == "__main__":
    main()
