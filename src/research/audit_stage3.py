"""Audit of the stage-3 extended panel: gaps, structural breaks, outliers, duplicate affiliations.

Writes results/research/stage3/audit_stage3.md (the text appended to DATA_AUDIT.md) and CSV tables.

  python -m src.research.audit_stage3
"""
import itertools

import numpy as np
import pandas as pd

from src.research import criterion_stage3 as C
from src.research.panel_stage3 import PANEL3_PATH, WORKS3_DIR
from src.research.stage2_config import SERIES_START_MIN_WORKS
from src.research.stage3 import OUT

BREAK_LOG_JUMP = np.log(2)      # works_count changes by more than x2 / /2 in one year
OUTLIER_Z = 3.5                 # robust z of log growth (median / MAD) within the university
DUPLICATE_SHARE = 0.10          # flag a pair if shared works exceed 10% of the smaller university


def gaps(panel):
    rows = []
    for uni, g in panel.groupby("uni"):
        w = g.set_index("year")["works_count"].reindex(range(C.PANEL_YEARS[0], C.PANEL_YEARS[1] + 1), fill_value=0)
        start = w[w >= SERIES_START_MIN_WORKS].index.min()
        after = w.loc[start:]
        rows.append({"uni": uni, "series_start": start, "years_below_20_after_start":
                     int((after < C.SERIES_MIN_WORKS_PER_YEAR).sum()), "zero_years_after_start": int((after == 0).sum())})
    return pd.DataFrame(rows)


def breaks_outliers(panel):
    rows = []
    cols = ["works_count", "unique_authors", "citations_received_in_year", "n_intl_works",
            "n_partner_countries", "n_partner_institutions"]
    for uni, g in panel.groupby("uni"):
        g = g.set_index("year").sort_index()
        for c in cols:
            s = g[c].where(g[c] > 0).where(g["works_count"] >= SERIES_START_MIN_WORKS)
            d = np.log(s).diff().dropna()
            if len(d) < 4:
                continue
            mad = (d - d.median()).abs().median() * 1.4826
            z = (d - d.median()) / mad if mad > 0 else d * 0
            for y, v in d.items():
                if (c == "works_count" and abs(v) > BREAK_LOG_JUMP) or abs(z[y]) > OUTLIER_Z:
                    rows.append({"uni": uni, "column": c, "year": int(y), "log_growth": round(float(v), 3),
                                 "robust_z": round(float(z[y]), 1),
                                 "type": "break (x2)" if c == "works_count" and abs(v) > BREAK_LOG_JUMP else "outlier"})
    return pd.DataFrame(rows)


def duplicates(panel):
    ids = {}
    for f in WORKS3_DIR.glob("*.parquet"):
        w = pd.read_parquet(f, columns=["uni", "id", "year"])
        w = w[w["year"].between(*C.PANEL_YEARS)]
        if len(w):
            ids[w["uni"].iloc[0]] = set(w["id"])
    keep = set(panel["uni"])
    rows = []
    for a, b in itertools.combinations(sorted(k for k in ids if k in keep), 2):
        shared = len(ids[a] & ids[b])
        small = min(len(ids[a]), len(ids[b]))
        if shared:
            rows.append({"uni_a": a, "uni_b": b, "shared_works": shared, "share_of_smaller": shared / small,
                         "flag": shared / small > DUPLICATE_SHARE})
    return pd.DataFrame(rows).sort_values("share_of_smaller", ascending=False)


def main():
    panel = pd.read_parquet(PANEL3_PATH)
    names = panel.groupby("uni")["name"].first()
    g, b, d = gaps(panel), breaks_outliers(panel), duplicates(panel)
    for df, name in ((g, "audit_gaps"), (b, "audit_breaks_outliers"), (d, "audit_duplicates")):
        df.to_csv(OUT / f"{name}.csv", index=False)
    lines = ["Пропуски (годы < 20 работ после начала ряда):", ""]
    gg = g[g["years_below_20_after_start"] > 0]
    lines += [f"- {names[r.uni]} ({r.uni}): {r.years_below_20_after_start} лет < 20 работ, начало ряда {r.series_start}"
              for r in gg.itertuples()] or ["- нет"]
    bb = b[b["type"] == "break (x2)"]
    lines += ["", f"Разрывы works_count (рост или падение более чем вдвое за год): {len(bb)}", ""]
    lines += [f"- {names[r.uni]}: {r.year}, log-рост {r.log_growth}" for r in bb.itertuples()] or ["- нет"]
    oo = b[b["type"] == "outlier"]
    lines += ["", f"Выбросы (|robust z| > {OUTLIER_Z} логарифмического роста внутри вуза): {len(oo)} точек; "
              "по столбцам: " + ", ".join(f"{k} {v}" for k, v in oo["column"].value_counts().items()), ""]
    dd = d[d["flag"]]
    lines += [f"Дубли аффилиаций (общие работы > {DUPLICATE_SHARE:.0%} меньшего вуза): {len(dd)} пар", ""]
    lines += [f"- {names.get(r.uni_a, r.uni_a)} × {names.get(r.uni_b, r.uni_b)}: {r.shared_works} общих работ "
              f"({r.share_of_smaller:.1%} меньшего)" for r in dd.itertuples()] or ["- нет"]
    text = "\n".join(lines)
    (OUT / "audit_stage3.md").write_text(text)
    print(text)


if __name__ == "__main__":
    main()
