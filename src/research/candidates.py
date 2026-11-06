"""Stage 3 university selection by the pre-registered rules (src/research/criterion_stage3.py).

Every candidate gets a row in results/research/stage3/candidates.csv: selected, or the reason it is not.
Uses OpenAlex institutions and group_by counts (cheap) and the free ROR API; no works are downloaded here.

  python -m src.research.candidates
"""
import re
from datetime import date

import numpy as np
import pandas as pd

from src.research import openalex_client as oa
from src.research import criterion_stage3 as C
from src.research.config import RESEARCH_RESULTS_DIR
from src.research.institutions import UNIVERSITIES

OUT = RESEARCH_RESULTS_DIR / "stage3" / "candidates.csv"
SELECT = "id,display_name,ror,country_code,works_count,type"
TECH = re.compile(C.TECH_NAME_PATTERN, re.I)
NON_UNI_NAME = re.compile(C.NON_UNIVERSITY_NAME, re.I)


def _list(filter_: str) -> list[dict]:
    out, page = [], 1
    while True:
        d = oa.get("institutions", {"filter": filter_, "per_page": 200, "page": page, "select": SELECT})
        out += d["results"]
        if page * 200 >= d["meta"]["count"] or not d["results"]:
            return out
        page += 1


def _short(url):
    return url.rsplit("/", 1)[-1] if url else None


def ror_info(ror_url: str | None) -> dict:
    if not ror_url:
        return {"ror_status": None, "established": None, "ror_types": None, "ror_parent": None}
    try:
        r = oa.fetch_ror(ror_url)
        parents = [x["label"] for x in r.get("relationships") or [] if x.get("type") == "parent"]
        return {"ror_status": r.get("status"), "established": r.get("established"),
                "ror_types": ",".join(r.get("types") or []), "ror_parent": "; ".join(parents) or None}
    except Exception as exc:  # network or 404
        return {"ror_status": f"error {type(exc).__name__}", "established": None, "ror_types": None,
                "ror_parent": None}


def series_rule(openalex_id: str) -> dict:
    """>= 8 consecutive years in 2010-2025 with >= 20 works (retracted and paratext excluded)."""
    g = oa.group_by(f"institutions.id:{openalex_id},is_retracted:false,is_paratext:false,"
                    f"publication_year:{C.PANEL_YEARS[0]}-{C.PANEL_YEARS[1]}", "publication_year")
    counts = {int(x["key"]): int(x["count"]) for x in g}
    ok = [y for y in range(C.PANEL_YEARS[0], C.PANEL_YEARS[1] + 1) if counts.get(y, 0) >= C.SERIES_MIN_WORKS_PER_YEAR]
    best_len, best_start, run_start, prev = 0, None, None, None
    for y in ok:
        run_start = y if prev is None or y != prev + 1 else run_start
        if y - run_start + 1 > best_len:
            best_len, best_start = y - run_start + 1, run_start
        prev = y
    return {"longest_run": best_len, "series_start": best_start,
            "works_2010_2025": sum(counts.get(y, 0) for y in range(C.PANEL_YEARS[0], C.PANEL_YEARS[1] + 1)),
            "series_ok": best_len >= C.SERIES_MIN_CONSECUTIVE_YEARS}


def main():
    rows = []
    current = {u.openalex_id: u for u in UNIVERSITIES}
    for r in _list("country_code:KZ,works_count:>999"):
        rows.append({**r, "group": "A_kz_1000"})
    regional = "|".join(c for cs in C.REGION_COUNTRIES.values() for c in cs if c != "KZ")
    for r in _list(f"country_code:{regional},works_count:>999"):
        if TECH.search(r["display_name"] or ""):
            rows.append({**r, "group": "B_young_tech_region"})
    for oid, u in current.items():
        if not any(_short(r["id"]) == oid for r in rows):
            inst = oa.fetch_institution(oid)
            rows.append({"id": inst["id"], "display_name": inst["display_name"], "ror": inst.get("ror"),
                         "country_code": inst.get("country_code"), "works_count": inst.get("works_count"),
                         "type": inst.get("type"), "group": "C_current_panel"})
    df = pd.DataFrame(rows)
    df["openalex_id"] = df["id"].map(_short)
    df = df.drop_duplicates("openalex_id")
    df["in_current_panel"] = df["openalex_id"].isin(current)
    df["region"] = df["country_code"].map({c: k for k, cs in C.REGION_COUNTRIES.items() for c in cs}).fillna("world")
    ror = pd.DataFrame([ror_info(x) for x in df["ror"]], index=df.index)
    df = pd.concat([df, ror], axis=1)
    df["ror_shared_by"] = df.groupby("ror")["openalex_id"].transform("count").where(df["ror"].notna(), 0)

    decisions = []
    for _, r in df.iterrows():
        reason = None
        degree = C.DEGREE_CHECK.get(r["openalex_id"])
        if r["type"] != "education":
            reason = f"не университет (тип OpenAlex: {r['type']})"
        elif not r["ror"]:
            reason = "нет ROR"
        elif r["ror_shared_by"] > 1:
            reason = "ROR не однозначен (несколько ID OpenAlex)"
        elif r["ror_status"] != "active":
            reason = f"ROR не активен ({r['ror_status']})"
        elif r["group"] == "B_young_tech_region" and not (pd.notna(r["established"]) and
                                                         r["established"] >= C.GROUP_B["established_min"]):
            reason = f"основан до 2000 или год неизвестен ({r['established']})"
        elif isinstance(r["ror_parent"], str):
            reason = f"подразделение другой организации (ROR parent: {r['ror_parent']})"
        elif degree is not None and not degree[0]:
            reason = f"исследовательский институт, не вуз ({degree[1]})"
        elif not NON_UNI_NAME.search(r["display_name"] or "") and degree is None:
            reason = "нет ручной проверки статуса вуза (D6)"
        decisions.append(reason)
    df["pre_series_reason"] = decisions
    series = {}
    for _, r in df[df["pre_series_reason"].isna()].iterrows():
        series[r["openalex_id"]] = series_rule(r["openalex_id"])
    s = pd.DataFrame.from_dict(series, orient="index")
    df = df.join(s, on="openalex_id")
    df["selected"] = df["pre_series_reason"].isna() & df["series_ok"].fillna(False).astype(bool)
    df["reason"] = np.where(df["selected"], "отобран",
                            df["pre_series_reason"].fillna("меньше 8 лет подряд с ≥ 20 работами"))
    sdu = df["openalex_id"] == "I4210120897"
    df.loc[sdu, "reason"] = np.where(df.loc[sdu, "selected"], "отобран; только анализ чувствительности (правило SDU)",
                                     df.loc[sdu, "reason"])
    n_sel = int((df["selected"] & ~sdu).sum())
    df["world_draw_needed"] = n_sel < C.TARGET_PANEL_SIZE[0]
    df["extracted"] = date.today().isoformat()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df["degree_check"] = df["openalex_id"].map(lambda i: C.DEGREE_CHECK.get(i, (None, None))[1])
    cols = ["openalex_id", "display_name", "type", "country_code", "region", "group", "in_current_panel", "ror",
            "ror_status", "ror_types", "ror_parent", "degree_check", "established", "works_count", "works_2010_2025", "longest_run", "series_start",
            "selected", "reason", "world_draw_needed", "extracted"]
    df[cols].sort_values(["selected", "group", "works_count"], ascending=[False, True, False]).to_csv(OUT, index=False)
    print(df.groupby(["group", "selected"]).size())
    print("selected (main, without SDU):", n_sel, "| world draw needed:", n_sel < C.TARGET_PANEL_SIZE[0])
    print(oa.log_usage("stage3_candidates"))


if __name__ == "__main__":
    main()
