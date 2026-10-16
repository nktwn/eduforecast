"""Finance stage 5: benchmark of expense structure for US peer groups.

Distribution (P10, P25, P50, P75, P90) of expense shares for groups sector x Carnegie x size
tercile, and the gap of a value relative to the group median in IQR units. Shares are
structural (comparable across currencies); sums in tenge are never compared.

  python -m src.finance.benchmark
"""
import numpy as np
import pandas as pd

from src.finance.config import FINANCE_RESULTS_DIR
from src.finance.panel import CATEGORIES
from src.finance.panel_stage2 import PANEL2_PATH

OUT_PATH = FINANCE_RESULTS_DIR / "stage2" / "benchmark_shares.csv"
PERCENTILES = (10, 25, 50, 75, 90)
DEFAULT_YEARS = (2021, 2023)
MIN_GROUP = 10
OPS = [c for c in CATEGORIES if c != "scholarships"]
SHARES = [f"{c}_share_ops" for c in OPS] + ["nat_compensation_share", "nat_depreciation_share",
                                            "nat_interest_share", "nat_other_incl_om_share"]
LABELS = {
    "instruction_share_ops": "Преподавание / 6 операционных функций",
    "research_share_ops": "Исследования / 6 операционных функций",
    "public_service_share_ops": "Общественные услуги / 6 операционных функций",
    "academic_support_share_ops": "Академическая поддержка / 6 операционных функций",
    "student_services_share_ops": "Студенческие сервисы / 6 операционных функций",
    "institutional_support_share_ops": "Институциональная поддержка / 6 операционных функций",
    "nat_compensation_share": "Оплата труда (зарплаты + льготы) / все расходы",
    "nat_depreciation_share": "Амортизация / все расходы",
    "nat_interest_share": "Проценты / все расходы",
    "nat_other_incl_om_share": "Прочие расходы с O&M / все расходы",
}


def institution_means(panel: pd.DataFrame, years=DEFAULT_YEARS) -> pd.DataFrame:
    """One row per series: mean shares over the year window, latest group attributes."""
    p = panel[~panel["superseded"] & panel["year"].between(*years)].copy()
    ops_total = p[[f"exp_{c}" for c in OPS]].sum(axis=1, min_count=len(OPS))
    for c in OPS:
        p[f"{c}_share_ops"] = p[f"exp_{c}"] / ops_total.where(ops_total > 0)
    size = np.log(panel.loc[~panel["superseded"], "fte_total"].where(lambda s: s > 0)).groupby(
        panel["series_id"]).median()
    tercile = pd.qcut(size, 3, labels=["small", "medium", "large"])
    attrs = p.sort_values("year").groupby("series_id")[["name", "control_label", "carnegie_group"]].last()
    out = p.groupby("series_id")[SHARES].mean().join(attrs)
    out["size_tercile"] = out.index.map(tercile)
    return out


def distribution(inst: pd.DataFrame, by=("control_label", "carnegie_group", "size_tercile")) -> pd.DataFrame:
    rows = []
    for key, g in inst.groupby(list(by), observed=True):
        for share in SHARES:
            v = g[share].dropna()
            row = dict(zip(by, key), metric=share, n=len(v))
            row.update({f"p{q}": (np.percentile(v, q) if len(v) >= MIN_GROUP else np.nan) for q in PERCENTILES})
            rows.append(row)
    return pd.DataFrame(rows)


def peer_distribution(inst: pd.DataFrame, metric: str, control: str | None = None,
                      carnegie: list[str] | None = None, size: list[str] | None = None) -> dict:
    g = inst
    if control:
        g = g[g["control_label"] == control]
    if carnegie:
        g = g[g["carnegie_group"].isin(carnegie)]
    if size:
        g = g[g["size_tercile"].isin(size)]
    v = g[metric].dropna()
    if len(v) < MIN_GROUP:
        return {"n": len(v)}
    return {"n": len(v), **{f"p{q}": float(np.percentile(v, q)) for q in PERCENTILES}}


def gap(value: float, dist: dict) -> dict:
    """Gap relative to the group median in IQR units, and the position among the percentiles."""
    if value is None or np.isnan(value) or "p50" not in dist:
        return {"gap_iqr": np.nan, "position": "нет данных"}
    iqr = dist["p75"] - dist["p25"]
    g = (value - dist["p50"]) / iqr if iqr > 0 else np.nan
    if value < dist["p10"]:
        pos = "ниже P10"
    elif value > dist["p90"]:
        pos = "выше P90"
    elif dist["p25"] <= value <= dist["p75"]:
        pos = "в межквартильном размахе"
    else:
        pos = "между P10 и P90, вне межквартильного размаха"
    return {"gap_iqr": g, "position": pos}


def main():
    panel = pd.read_parquet(PANEL2_PATH)
    dist = distribution(institution_means(panel))
    dist.to_csv(OUT_PATH, index=False)
    pd.set_option("display.width", 250)
    print(dist[dist["metric"].isin(["instruction_share_ops", "nat_compensation_share"])].round(3).head(30)
          .to_string(index=False))


if __name__ == "__main__":
    main()
