import re

import pandas as pd

from src.research import openalex_client as oa
from src.research.config import PANEL_YEAR_MAX, PANEL_YEAR_MIN
from src.research.institutions import BY_KEY
from src.research.stage2_config import (
    SDU_MAX_MISATTRIBUTED_TOTAL,
    SDU_MAX_MISATTRIBUTED_YEAR,
    STAGE2_DIR,
)

SDU = BY_KEY["SDU"]
CHECK_YEARS = range(2017, PANEL_YEAR_MAX + 1)
KZ_MARKERS = re.compile(r"kazakh|almaty|kaskelen|qaskelen|sdu university|казахстан|қазақстан|алматы|каскелен", re.I)
TR_MARKERS = re.compile(r"isparta|turkey|türkiye|turkiye|üniversitesi|universitesi", re.I)


def _classify_page(data: dict) -> dict:
    inst_url = f"https://openalex.org/{SDU.openalex_id}"
    out = []
    for work in data["results"]:
        strings = []
        for a in work.get("authorships") or []:
            if any(i.get("id") == inst_url for i in a.get("institutions") or []):
                strings.extend(a.get("raw_affiliation_strings") or [])
        text = " | ".join(strings)
        kz, tr = bool(KZ_MARKERS.search(text)), bool(TR_MARKERS.search(text))
        status = "kz" if kz else ("tr_only" if tr else "unknown")
        out.append({"id": work["id"], "year": work.get("publication_year"), "status": status, "raw": text[:300]})
    return {"meta": data["meta"], "results": out}


def run_check() -> pd.DataFrame:
    rows = []
    for year in range(PANEL_YEAR_MIN, PANEL_YEAR_MAX + 1):
        filter_ = f"institutions.id:{SDU.openalex_id},publication_year:{year}"
        rows.extend(oa.iter_works(filter_, "id,publication_year,is_retracted,is_paratext,authorships",
                                  transform=_classify_page))
    works = pd.DataFrame(rows)
    works.to_csv(STAGE2_DIR / "sdu_affiliation_works.csv", index=False)

    by_year = works.pivot_table(index="year", columns="status", values="id", aggfunc="count", fill_value=0)
    for col in ("kz", "tr_only", "unknown"):
        if col not in by_year:
            by_year[col] = 0
    by_year["works"] = by_year[["kz", "tr_only", "unknown"]].sum(axis=1)
    by_year["tr_only_share"] = by_year["tr_only"] / by_year["works"]
    by_year = by_year.reset_index()
    by_year.to_csv(STAGE2_DIR / "sdu_affiliation_check.csv", index=False)
    return by_year


def decide(by_year: pd.DataFrame) -> dict:
    window = by_year[by_year["year"].isin(CHECK_YEARS)]
    total_share = window["tr_only"].sum() / window["works"].sum()
    worst_year_share = window["tr_only_share"].max()
    passed = total_share <= SDU_MAX_MISATTRIBUTED_TOTAL and worst_year_share <= SDU_MAX_MISATTRIBUTED_YEAR
    return {"total_share_2017_2025": total_share, "worst_year_share": worst_year_share, "passed": bool(passed)}


def main():
    try:
        by_year = run_check()
    except oa.BudgetExhausted as exc:
        print(f"Stopped: {exc}. Rerun after the OpenAlex daily reset.")
        raise SystemExit(2)
    print(by_year.to_string(index=False))
    print(decide(by_year))


if __name__ == "__main__":
    main()
