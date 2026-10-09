from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.config import BASE_DIR
from src.research import openalex_client as oa
from src.research.config import METRICS_DIR, PANEL_PATH, PANEL_YEAR_MAX, PANEL_YEAR_MIN, PARTIAL_YEAR, WORKS_DIR
from src.research.institutions import UNIVERSITIES

FIG_DIR: Path = BASE_DIR / "docs" / "data_audit"
TABLES_PATH: Path = METRICS_DIR / "audit_tables.md"

SERIES = "#2a78d6"
PARTIAL = "#8a8984"
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e6e5e0"

AFFILIATION_QUERIES = {
    "NU": "Nazarbayev University",
    "KBTU": "Kazakh-British Technical University",
    "SDU": "Suleyman Demirel University",
    "SATBAYEV": "Satbayev University",
    "KAZNU": "Al-Farabi Kazakh National University",
    "ENU": "Eurasian National University",
    "NARXOZ": "Narxoz University",
    "KIMEP": "KIMEP",
    "SHAKARIM": "Shakarim University",
    "AITU": "Astana IT University",
    "SKOLTECH": "Skolkovo Institute of Science and Technology",
    "INNOPOLIS": "Innopolis University",
    "UNIST": "Ulsan National Institute of Science and Technology",
    "MBZUAI": "Mohamed bin Zayed University of Artificial Intelligence",
}

METRIC_LABELS = {
    "works_count": "Works per year",
    "citations_received_in_year": "Citations received in year",
    "unique_authors": "Unique affiliated authors",
    "intl_collab_share": "Share of works with ≥2 countries",
    "top10_share": "Share of works in global top-10% cited",
    "fwci_mean": "Mean FWCI",
    "oa_share": "Open-access share",
}
ORDER = [u.key for u in UNIVERSITIES]


def _style(ax):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=7, length=0)
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def small_multiples(panel: pd.DataFrame, metric: str, path: Path):
    fig, axes = plt.subplots(3, 5, figsize=(15, 8), sharex=True)
    for ax, key in zip(axes.flat, ORDER):
        g = panel[panel["uni"] == key].sort_values("year")
        full = g[~g["is_partial"]]
        part = g[g["year"] >= PARTIAL_YEAR - 1]
        ax.plot(full["year"], full[metric], color=SERIES, linewidth=2, marker="o", markersize=3)
        ax.plot(part["year"], part[metric], color=PARTIAL, linewidth=1.5, linestyle=":", marker="o",
                markersize=4, markerfacecolor="white", markevery=[len(part) - 1])
        ax.set_title(key, fontsize=9, color=INK, loc="left")
        ax.set_xticks([2010, 2015, 2020, 2025])
        ax.set_ylim(bottom=0)
        _style(ax)
    axes.flat[-1].axis("off")
    fig.suptitle(METRIC_LABELS.get(metric, metric), x=0.01, ha="left", fontsize=12, color=INK)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.text(0.01, 0.01, f"Solid: {PANEL_YEAR_MIN}–{PANEL_YEAR_MAX}.  Dotted to hollow point: {PARTIAL_YEAR}, "
             "partial year (data to October), not used for training or evaluation.", color=MUTED, fontsize=9)
    fig.savefig(path, dpi=110)
    plt.close(fig)


def coverage_heatmap(panel: pd.DataFrame, path: Path):
    m = panel.pivot(index="uni", columns="year", values="works_count").loc[ORDER]
    fig, ax = plt.subplots(figsize=(13, 5.5))
    im = ax.imshow(np.log10(m.to_numpy(float) + 1), cmap="Blues", aspect="auto")
    ax.set_xticks(range(m.shape[1]), m.columns, fontsize=8)
    ax.set_yticks(range(m.shape[0]), m.index, fontsize=8)
    for i in range(m.shape[0]):
        for j in range(m.shape[1]):
            v = int(m.iat[i, j])
            ax.text(j, i, v, ha="center", va="center", fontsize=6.5,
                    color="white" if np.log10(v + 1) > 2.6 else INK)
    ax.tick_params(length=0, colors=MUTED)
    for s in ax.spines.values():
        s.set_visible(False)
    cb = fig.colorbar(im, ax=ax, fraction=0.025)
    cb.set_label("log10(works + 1)", fontsize=8, color=MUTED)
    ax.set_title(f"Works per university and year (column {PARTIAL_YEAR} is partial)", loc="left", fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def citation_maturity(works: pd.DataFrame, path: Path) -> pd.DataFrame:
    w = works[works["year"].between(PANEL_YEAR_MIN, PARTIAL_YEAR)]
    by_year = w.groupby("year").agg(
        mean_citations=("cited_by_count", "mean"),
        share_uncited=("cited_by_count", lambda s: float((s.fillna(0) == 0).mean())),
        fwci_coverage=("fwci", lambda s: float(s.notna().mean())),
        pct_coverage=("pct_value", lambda s: float(s.notna().mean())),
    )
    fig, ax = plt.subplots(figsize=(8, 3.5))
    ax.bar(by_year.index, by_year["mean_citations"], color=SERIES, width=0.7)
    ax.set_title("Mean citations to date per work, by publication year (all 14 universities)",
                 loc="left", fontsize=10)
    _style(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return by_year


def yoy_breaks(panel: pd.DataFrame, metric: str = "works_count", min_base: int = 20) -> pd.DataFrame:
    rows = []
    for key, g in panel[~panel["is_partial"]].sort_values("year").groupby("uni"):
        prev = g[metric].shift()
        ratio = g[metric] / prev
        for (_, r), p, q in zip(g.iterrows(), prev, ratio):
            if pd.notna(p) and p >= min_base and (q >= 2 or q <= 0.6):
                rows.append({"uni": key, "year": r["year"], "prev": int(p), "value": int(r[metric]), "ratio": round(q, 2)})
    return pd.DataFrame(rows)


def robust_outliers(panel: pd.DataFrame, metrics: list[str], z: float = 3.5) -> pd.DataFrame:
    rows = []
    full = panel[(~panel["is_partial"]) & (panel["works_count"] >= 20)]
    for metric in metrics:
        for key, g in full.groupby("uni"):
            s = g.set_index("year")[metric].dropna()
            if len(s) < 5:
                continue
            d = s.diff().dropna()
            mad = (d - d.median()).abs().median()
            if mad == 0:
                continue
            score = 0.6745 * (d - d.median()) / mad
            for year, sc in score[score.abs() > z].items():
                rows.append({"uni": key, "metric": metric, "year": year, "value": round(s[year], 3),
                             "prev": round(s[year - 1], 3) if year - 1 in s else None, "robust_z": round(sc, 1)})
    return pd.DataFrame(rows)


def affiliation_checks() -> pd.DataFrame:
    rows = []
    years = f"publication_year:{PANEL_YEAR_MIN}-{PANEL_YEAR_MAX}"
    for u in UNIVERSITIES:
        try:
            rows.append(_affiliation_row(u, years))
        except oa.BudgetExhausted:
            rows.append({"uni": u.key, "raw_string_query": "pending: OpenAlex daily budget exhausted"})
    return pd.DataFrame(rows)


def _affiliation_row(u, years: str) -> dict:
    exact = oa.get("works", {"filter": f"institutions.id:{u.openalex_id},{years}", "per_page": 1})["meta"]["count"]
    lineage = oa.get("works", {"filter": f"authorships.institutions.lineage:{u.openalex_id},{years}",
                               "per_page": 1})["meta"]["count"]
    query = AFFILIATION_QUERIES[u.key]
    raw = oa.get("works", {"filter": f'raw_affiliation_strings.search:"{query}",{years}', "per_page": 1})["meta"]["count"]
    raw_not_linked = oa.get("works", {
        "filter": f'raw_affiliation_strings.search:"{query}",{years},institutions.id:!{u.openalex_id}',
        "per_page": 1,
    })["meta"]["count"]
    return {"uni": u.key, "exact_id": exact, "with_children": lineage, "children_extra": lineage - exact,
            "raw_string_query": query, "raw_string_match": raw, "raw_match_not_linked": raw_not_linked,
            "not_linked_pct": round(100 * raw_not_linked / max(exact, 1), 1)}


def consistency(panel: pd.DataFrame, works_by_uni: dict[str, pd.DataFrame], fields: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for key in ORDER:
        g = panel[panel["uni"] == key]
        w = works_by_uni[key]
        f = fields[fields["uni"] == key].groupby("year")["works"].sum()
        g_full = g[~g["is_partial"]]
        rows.append({
            "uni": key,
            "works_vs_groupby_maxdiff": int((g["works_count"] - g["openalex_groupby_works_count"]).abs().max()),
            "works_vs_inst_counts_maxdiff_pct": round(float(
                ((g_full["works_count"] - g_full["openalex_inst_works_count"]).abs()
                 / g_full["openalex_inst_works_count"].replace(0, np.nan)).max() * 100), 1),
            "oa_vs_inst_oa_maxdiff_pct": round(float(
                ((g_full["oa_share"] * g_full["works_count"] - g_full["openalex_inst_oa_works_count"]).abs()
                 / g_full["openalex_inst_oa_works_count"].replace(0, np.nan)).max() * 100), 1),
            "no_primary_topic_pct": round(100 * (1 - f.sum() / len(w)), 2),
            "cites_by_year_sum_eq_cited_by": bool(
                w["cites_by_year"].map(lambda c: sum(x["cited_by_count"] for x in c)).sum()
                == w["cited_by_count"].sum()),
            "cites_received_before_min_year": int(min(
                (x["year"] for c in w["cites_by_year"] for x in c), default=0)),
            "duplicate_work_ids": int(w["id"].duplicated().sum()),
            "retracted": int(w["is_retracted"].fillna(False).sum()),
            "paratext": int(w["is_paratext"].fillna(False).sum()),
            "truncated_authorships": int((w["n_authorships"] >= 100).sum()),
            "no_affiliated_author_id_pct": round(100 * float((w["affiliated_authors"].str.len() == 0).mean()), 2),
        })
    return pd.DataFrame(rows)


def main():
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    panel = pd.read_parquet(PANEL_PATH)
    fields = pd.read_parquet(PANEL_PATH.parent / "field_shares.parquet")
    works_by_uni = {k: pd.read_parquet(WORKS_DIR / f"{k}.parquet") for k in ORDER}
    all_works = pd.concat(works_by_uni.values(), ignore_index=True)

    coverage_heatmap(panel, FIG_DIR / "coverage_heatmap.png")
    for metric in METRIC_LABELS:
        small_multiples(panel, metric, FIG_DIR / f"series_{metric}.png")
    maturity = citation_maturity(all_works, FIG_DIR / "citation_maturity.png")

    full = panel[~panel["is_partial"]]
    first_years = full[full["works_count"] > 0].groupby("uni")["year"].min()
    first10 = full[full["works_count"] >= 10].groupby("uni")["year"].min()
    missing = pd.DataFrame({
        "first_year_any": first_years, "first_year_ge10": first10,
        "zero_years": full.assign(z=full["works_count"] == 0).groupby("uni")["z"].sum(),
        "works_2010_2025": full.groupby("uni")["works_count"].sum(),
        "works_2026_partial": panel[panel["is_partial"]].set_index("uni")["works_count"],
    }).loc[ORDER]
    nan_cols = full.isna().sum()
    nan_cols = nan_cols[nan_cols > 0]

    sections = {
        "missing_by_uni": missing.reset_index().rename(columns={"index": "uni"}),
        "nan_columns": nan_cols.rename("nan_rows").reset_index().rename(columns={"index": "column"}),
        "consistency": consistency(panel, works_by_uni, fields),
        "affiliation": affiliation_checks(),
        "yoy_breaks": yoy_breaks(panel),
        "robust_outliers": robust_outliers(panel, list(METRIC_LABELS)),
        "citation_maturity": maturity.round(3).reset_index(),
        "authors_vs_works_2025": full[full["year"] == PANEL_YEAR_MAX][
            ["uni", "works_count", "unique_authors", "truncated_authorships_works",
             "works_without_affiliated_author_id"]],
    }
    with open(TABLES_PATH, "w", encoding="utf-8") as f:
        for name, df in sections.items():
            f.write(f"## {name}\n\n{df.to_markdown(index=False)}\n\n")
    print(f"Wrote {TABLES_PATH} and figures to {FIG_DIR}; budget={oa.budget()}")


if __name__ == "__main__":
    main()
