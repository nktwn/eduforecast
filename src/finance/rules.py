"""Finance stage 5: rule flags for the AITU profile; thresholds and their sources in rules.yaml.

  python -m src.finance.rules
"""
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from src.finance import aitu_profile
from src.finance.benchmark import gap, institution_means, peer_distribution

RULES_PATH = Path(__file__).with_name("rules.yaml")
ALLOWED_SOURCES = {"law", "university_document", "supervisor", "us_peer_percentile"}
REQUIRED_STATUS = {"supervisor": "уточнить", "us_peer_percentile": "ориентир США, контекст другой"}


def load_rules(path=RULES_PATH) -> dict:
    cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    for r in cfg["rules"]:
        src = r.get("source") or {}
        if src.get("type") not in ALLOWED_SOURCES or not src.get("text"):
            raise ValueError(f"rule {r['id']}: threshold without an allowed source")
        need = REQUIRED_STATUS.get(src["type"])
        if need and src.get("status") != need:
            raise ValueError(f"rule {r['id']}: source type {src['type']} requires status '{need}'")
    return cfg


def evaluate(profile: pd.DataFrame, panel: pd.DataFrame | None = None, cfg: dict | None = None) -> pd.DataFrame:
    """One row per (rule, year). `triggered` is None when the metric or the benchmark is unavailable."""
    cfg = cfg or load_rules()
    peers = cfg["us_peer_group"]
    inst = institution_means(panel, tuple(peers["years"])) if panel is not None else None
    rows = []
    for r in cfg["rules"]:
        for year in profile.index:
            value = profile.at[year, r["metric"]] if r["metric"] in profile.columns else np.nan
            row = {"rule": r["id"], "label": r["label"], "year": int(year), "value": value,
                   "severity": r["severity"], "source_type": r["source"]["type"], "source": r["source"]["text"],
                   "status": r["source"]["status"], "caveat": r.get("caveat", ""), "threshold": None,
                   "triggered": None, "message": ""}
            if pd.isna(value):
                row["message"] = "нет данных для расчёта"
            elif r["op"] == "outside_percentiles":
                if inst is None:
                    row["message"] = "нет данных США (панель не загружена)"
                else:
                    dist = peer_distribution(inst, r["benchmark_metric"], peers["control"], peers["carnegie"])
                    if "p50" not in dist:
                        row["message"] = f"мало аналогов США (n={dist['n']})"
                    else:
                        lo, hi = dist[f"p{r['low']}"], dist[f"p{r['high']}"]
                        g = gap(value, dist)
                        row.update(threshold=f"P{r['low']}–P{r['high']} = {lo:.3f}–{hi:.3f} (n={dist['n']}, "
                                             f"медиана {dist['p50']:.3f})",
                                   triggered=bool(value < lo or value > hi), gap_iqr=g["gap_iqr"],
                                   position=g["position"])
                        row["message"] = r["message"] if row["triggered"] else g["position"]
            else:
                ops = {"<": value < r["threshold"], ">": value > r["threshold"]}
                row.update(threshold=f"{r['op']} {r['threshold']}", triggered=bool(ops[r["op"]]))
                row["message"] = r["message"] if row["triggered"] else "условие не выполнено"
            rows.append(row)
    return pd.DataFrame(rows)


def evaluate_variants(df: pd.DataFrame, panel: pd.DataFrame | None = None, cfg: dict | None = None) -> pd.DataFrame:
    """All rules on all expenses, plus expense-share rules without the one-off 2019-2020 item."""
    cfg = cfg or load_rules()
    full = evaluate(aitu_profile.structure(df), panel, cfg).assign(variant="all")
    shares = [r["id"] for r in cfg["rules"] if r["metric"].endswith("_in_expenses")]
    excl = evaluate(aitu_profile.structure(df, exclude_one_off=True), panel, cfg)
    excl = excl[excl["rule"].isin(shares)].assign(variant="excl_one_off")
    out = pd.concat([full, excl], ignore_index=True)
    out["variant_label"] = out["variant"].map(aitu_profile.VARIANTS)
    return out


def main():
    from src.finance.panel_stage2 import PANEL2_PATH

    panel = pd.read_parquet(PANEL2_PATH) if PANEL2_PATH.exists() else None
    res = evaluate_variants(aitu_profile.load(), panel)
    from src.finance.models_stage2 import OUT_DIR
    res.to_csv(OUT_DIR / "aitu_rules.csv", index=False)
    pd.set_option("display.width", 250, "display.max_colwidth", 70)
    print(res[["variant", "rule", "year", "value", "threshold", "triggered", "message"]].to_string(index=False))


if __name__ == "__main__":
    main()
