import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.finance.config import FIG_DIR, FINANCE_RESULTS_DIR, INSTITUTIONS_PATH, PANEL_PATH, YEAR_MAX, YEAR_MIN, YEARS
from src.finance.panel import CATEGORIES

TABLES_PATH = FINANCE_RESULTS_DIR / "audit_tables.md"
SERIES = {"public": "#2a78d6", "private_nonprofit": "#eb6834"}
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e6e5e0"
KEY_VARS = ["fall_enrollment", "fte_total", "retention_rate", "grad_rate_150", "faculty_ft_instructional",
            "exp_total", "total_per_fte", "instruction_per_fte", "instruction_share"]
TARGETS = ["retention_rate", "grad_rate_150", "fall_enrollment", "total_per_fte"]


def _style(ax, title):
    ax.set_title(title, loc="left", fontsize=10, color=INK)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=8, length=0)
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def by_control_median(p, col):
    return p.groupby(["year", "control_label"])[col].median().unstack()


def plot_medians(p, cols_titles, path, log_growth=False):
    fig, axes = plt.subplots(2, (len(cols_titles) + 1) // 2, figsize=(14, 7))
    for ax, (col, title) in zip(axes.flat, cols_titles):
        m = by_control_median(p, col)
        for ctrl, color in SERIES.items():
            if ctrl in m:
                ax.plot(m.index, m[ctrl], color=color, linewidth=2, marker="o", markersize=3, label=ctrl)
        for x in (2012, 2016):
            ax.axvline(x, color=GRID, linewidth=1, linestyle=":")
        _style(ax, title)
    for ax in list(axes.flat)[len(cols_titles):]:
        ax.axis("off")
    axes.flat[0].legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def yoy(p, col):
    q = p[["unitid", "year", "control_label", "finance_form", col]].dropna().copy()
    q = q[q[col] > 0] if col not in ("retention_rate", "grad_rate_150") else q
    q = q.sort_values(["unitid", "year"])
    prev = q.groupby("unitid")[[col, "year"]].shift()
    consecutive = prev["year"] == q["year"] - 1
    if col in ("retention_rate", "grad_rate_150"):
        q["change"] = (q[col] - prev[col]).where(consecutive)
    else:
        q["change"] = np.log(q[col] / prev[col]).where(consecutive)
    q["prev_form"] = q.groupby("unitid")["finance_form"].shift().where(consecutive)
    return q.dropna(subset=["change"])


def breaks_table(p):
    rows = []
    for col in ["total_per_fte", "instruction_per_fte", "institutional_support_per_fte", "scholarships_per_fte",
                "fte_total", "fall_enrollment", "faculty_ft_instructional", "retention_rate", "grad_rate_150"]:
        q = yoy(p, col)
        g = q.groupby(["year", "control_label"])["change"].median().unstack()
        for year, r in g.iterrows():
            rows.append({"variable": col, "year": year, **{f"median_change_{k}": v for k, v in r.items()}})
    return pd.DataFrame(rows)


def outliers(p):
    out = []
    checks = {
        "total_per_fte > 99.5th pct or < 0.5th pct": (p["total_per_fte"] > p["total_per_fte"].quantile(0.995))
        | (p["total_per_fte"] < p["total_per_fte"].quantile(0.005)),
        "fte_total < 100": p["fte_total"] < 100,
        "exp_total <= 0": p["exp_total"] <= 0,
        "any category < 0": (p[[f"exp_{c}" for c in CATEGORIES]] < 0).any(axis=1),
        "core_total > total * 1.01": p["exp_core_total"] > p["exp_total"] * 1.01,
        "share sum > 1.01": p[[f"{c}_share" for c in CATEGORIES]].sum(axis=1) > 1.01,
        "retention = 0 or 100": p["retention_rate"].isin([0, 100]),
        "grad_rate = 0 or 100": p["grad_rate_150"].isin([0, 100]),
        "grad cohort < 30": p["grad_cohort"] < 30,
        "fte_per_faculty > 100": p["fte_per_faculty"] > 100,
    }
    for name, mask in checks.items():
        out.append({"check": name, "rows": int(mask.sum()), "institutions": int(p.loc[mask, "unitid"].nunique())})
    for col, thr in (("total_per_fte", 0.5), ("fall_enrollment", 0.5), ("retention_rate", 20), ("grad_rate_150", 20)):
        q = yoy(p, col)
        mask = q["change"].abs() > thr
        unit = "log" if col in ("total_per_fte", "fall_enrollment") else "pp"
        out.append({"check": f"|YoY change| {col} > {thr} {unit}", "rows": int(mask.sum()),
                    "institutions": int(q.loc[mask, "unitid"].nunique())})
    return pd.DataFrame(out)


def full_series(p):
    rows = []
    n_years = len(YEARS)
    for col in TARGETS + ["faculty_ft_instructional"]:
        counts = p.dropna(subset=[col]).groupby("unitid")["year"].nunique()
        rows.append({"variable": col, "institutions_any": len(counts), "institutions_all_14_years": int((counts == n_years).sum()),
                     "institutions_ge_10_years": int((counts >= 10).sum())})
    complete = p.dropna(subset=TARGETS).groupby("unitid")["year"].nunique()
    rows.append({"variable": "all 4 targets jointly", "institutions_any": len(complete),
                 "institutions_all_14_years": int((complete == n_years).sum()),
                 "institutions_ge_10_years": int((complete >= 10).sum())})
    return pd.DataFrame(rows)


def entries_exits(p, hd):
    hd = hd.rename(columns={"UNITID": "unitid"})
    span = p.groupby("unitid")["year"].agg(["min", "max", "nunique"])
    rows = []
    for unitid, r in span.iterrows():
        rec = {"unitid": unitid, "first": r["min"], "last": r["max"], "years": r["nunique"],
               "gaps": r["max"] - r["min"] + 1 - r["nunique"]}
        if r["max"] < YEAR_MAX:
            later = hd[(hd["unitid"] == unitid) & (hd["year"] > r["max"])]
            last_hd = hd[(hd["unitid"] == unitid) & (hd["year"] == r["max"])].iloc[0]
            newid = pd.to_numeric(pd.Series([last_hd.get("NEWID")]), errors="coerce").iloc[0]
            closed = str(last_hd.get("CLOSEDAT", "-2")).strip() not in ("-2", "", "nan", "-1")
            if not later.empty:
                after = later.sort_values("year").iloc[0]
                newid_after = pd.to_numeric(pd.Series([after.get("NEWID")]), errors="coerce").iloc[0]
                if newid_after and newid_after > 0:
                    rec["exit"] = "merged"
                elif str(after.get("CLOSEDAT", "-2")).strip() not in ("-2", "", "nan", "-1"):
                    rec["exit"] = "closed"
                else:
                    rec["exit"] = "left scope (level/control/offering changed)"
            elif newid and newid > 0:
                rec["exit"] = "merged"
            elif closed:
                rec["exit"] = "closed"
            else:
                rec["exit"] = "disappeared from IPEDS"
            rec["newid"] = newid if newid and newid > 0 else None
        if r["min"] > YEAR_MIN:
            earlier = hd[(hd["unitid"] == unitid) & (hd["year"] < r["min"])]
            rec["entry"] = "entered scope" if not earlier.empty else "new in IPEDS"
        rows.append(rec)
    return pd.DataFrame(rows)


def missing_by_year(p):
    return p.groupby("year")[KEY_VARS].apply(lambda d: d.isna().mean().round(3) * 100).T


def main():
    p = pd.read_parquet(PANEL_PATH)
    hd = pd.read_parquet(INSTITUTIONS_PATH)

    size = p.groupby(["year", "control_label"]).size().unstack()
    forms = p.groupby(["year", "control_label", "finance_form"], dropna=False).size().unstack().fillna(0).astype(int)
    switches = p.sort_values(["unitid", "year"]).groupby("unitid")["finance_form"].apply(
        lambda s: s.dropna().ne(s.dropna().shift()).iloc[1:].sum() if s.notna().sum() > 1 else 0)
    parent_child = p.groupby(["year", "prch_f"]).size().unstack().fillna(0).astype(int)
    ee = entries_exits(p, hd)
    breaks = breaks_table(p)

    plot_medians(p, [("total_per_fte", "Total expenses per FTE, median (nominal $)"),
                     ("instruction_per_fte", "Instruction per FTE, median"),
                     ("instruction_share", "Instruction share of total"),
                     ("institutional_support_share", "Institutional support share"),
                     ("retention_rate", "Full-time retention rate, median %"),
                     ("grad_rate_150", "Graduation rate 150%, median %"),
                     ("fte_total", "12-month FTE, median"),
                     ("fte_per_faculty", "FTE per full-time instructional staff")],
                 FIG_DIR / "medians_by_year.png")

    fig, axes = plt.subplots(1, 3, figsize=(15, 4))
    for ax, col, title in zip(axes, ["total_per_fte", "fall_enrollment", "faculty_ft_instructional"],
                              ["YoY log change, total expenses per FTE", "YoY log change, fall enrollment",
                               "YoY log change, FT instructional staff"]):
        q = yoy(p, col)
        data = [q.loc[q["year"] == y, "change"].clip(-1, 1) for y in YEARS[1:]]
        ax.boxplot(data, positions=YEARS[1:], widths=0.6, showfliers=False,
                   medianprops={"color": "#2a78d6", "linewidth": 2}, boxprops={"color": MUTED},
                   whiskerprops={"color": MUTED}, capprops={"color": MUTED})
        ax.axhline(0, color=GRID)
        ax.set_xticks(YEARS[1:], [str(y)[2:] for y in YEARS[1:]])
        _style(ax, title)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "yoy_change_boxplots.png", dpi=110)
    plt.close(fig)

    shares = p.groupby(["year", "finance_form"])[[f"{c}_share" for c in CATEGORIES]].median()

    sections = {
        "panel_size_by_year": size.reset_index(),
        "finance_form_by_year": forms.reset_index(),
        "form_switches": pd.DataFrame({"institutions_switching_form": [int((switches > 0).sum())]}),
        "parent_child_finance_by_year": parent_child.reset_index(),
        "missing_pct_by_year": missing_by_year(p).reset_index(),
        "full_series": full_series(p),
        "outliers": outliers(p),
        "median_shares_by_form": shares.round(3).reset_index(),
        "exits": ee["exit"].value_counts(dropna=True).rename_axis("exit").reset_index(name="institutions"),
        "exits_by_year": ee.dropna(subset=["exit"]).groupby(["last", "exit"]).size().unstack().fillna(0).astype(int).reset_index(),
        "entries": ee["entry"].value_counts(dropna=True).rename_axis("entry").reset_index(name="institutions"),
        "gaps": pd.DataFrame({"institutions_with_gaps": [int((ee["gaps"] > 0).sum())]}),
        "breaks_median_yoy": breaks.round(4),
    }
    with open(TABLES_PATH, "w", encoding="utf-8") as f:
        for name, df in sections.items():
            f.write(f"## {name}\n\n{df.to_markdown(index=False)}\n\n")
    ee.to_csv(FINANCE_RESULTS_DIR / "entries_exits.csv", index=False)
    print(f"Wrote {TABLES_PATH}")


if __name__ == "__main__":
    main()
