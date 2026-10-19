"""Stage 3 extended panel: university x year 2010-2025 for the universities selected by
src/research/candidates.py (pre-registered rules), with the international counts.

Same rules as stage 2 (src/research/panel.py functions are reused): retracted works and paratext
excluded, 2026 not used, authors counted only if affiliated with the university (id or lineage).
New per-year columns: n_partner_countries, n_intl_works, n_partner_institutions.
Resumable: every API page is cached on disk; finished universities are saved to WORKS3_DIR.

  python -m src.research.panel_stage3
"""
import json
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from src.research import openalex_client as oa
from src.research import panel as p2
from src.research.config import PANEL_YEAR_MAX, PANEL_YEAR_MIN, RESEARCH_DATA_DIR, RESEARCH_RESULTS_DIR
from src.research.institutions import UNIVERSITIES, University

WORKS3_DIR = RESEARCH_DATA_DIR / "works_stage3"
PANEL3_PATH = RESEARCH_DATA_DIR / "panel_stage3.parquet"
META3_PATH = RESEARCH_DATA_DIR / "panel_stage3_meta.json"
CANDIDATES = RESEARCH_RESULTS_DIR / "stage3" / "candidates.csv"
SELECTION_OUT = RESEARCH_RESULTS_DIR / "stage3" / "panel_universities.csv"
# a distinct select keeps the cache separate from stage 2 (whose cached pages lack institution ids)
WORK_SELECT3 = p2.WORK_SELECT + ",language"
EXTERNAL = {"I4405257690": "AITU", "I4210113480": "MBZUAI"}  # fail the series rule: benchmark/forecast only


def _short(url):
    return url.rsplit("/", 1)[-1] if url else None


def compact_work3(work: dict, inst_id: str) -> dict:
    out = p2._compact_work(work, inst_id)
    inst_url = f"https://openalex.org/{inst_id}"
    partners = set()
    for a in work.get("authorships") or []:
        for inst in a.get("institutions") or []:
            iid = inst.get("id")
            if iid and iid != inst_url and inst_url not in (inst.get("lineage") or []):
                partners.add(_short(iid))
    out["partner_institutions"] = sorted(partners)
    return out


def _page(inst_id):
    return lambda data: {"meta": data["meta"], "results": [compact_work3(w, inst_id) for w in data["results"]]}


def universities() -> list[tuple[University, str]]:
    c = pd.read_csv(CANDIDATES)
    keys = {u.openalex_id: u.key for u in UNIVERSITIES}
    out = []
    for _, r in c.iterrows():
        role = ("main" if r["selected"] and r["openalex_id"] != "I4210120897" else
                "sensitivity" if r["openalex_id"] == "I4210120897" else
                "external" if r["openalex_id"] in EXTERNAL else None)
        if role is None:
            continue
        key = keys.get(r["openalex_id"], r["openalex_id"])
        out.append((University(key, r["openalex_id"], r["display_name"], str(r["ror"]).rsplit("/", 1)[-1],
                               r["country_code"], r["group"]), role))
    return out


def _atomic_parquet(df: pd.DataFrame, path) -> None:
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    df.to_parquet(tmp, index=False)
    os.replace(tmp, path)


def _year_pages(uni: University, year: int):
    """All pages of one year (from the disk cache when present); returns works, expected count, page mtimes."""
    f = f"institutions.id:{uni.openalex_id},publication_year:{year}"
    works, mtimes, page, expected = [], [], 1, 0
    while True:
        params = {"filter": f, "select": WORK_SELECT3, "per_page": 200, "page": page}
        data = oa.get("works", params, transform=_page(uni.openalex_id))
        cache = oa._cache_path(f"{oa.OPENALEX_API_BASE}/works", params)
        mtimes.append(cache.stat().st_mtime)
        expected = data["meta"]["count"]
        works += data["results"]
        if len(data["results"]) < 200 or page * 200 >= expected:
            return works, expected, mtimes
        page += 1


def fetch(uni: University) -> tuple[pd.DataFrame, dict]:
    """Works of one university 2010-2025. The saved file is reused only if it passes the completeness check
    (every year has as many works as OpenAlex reported for it); otherwise it is rebuilt from the cache."""
    path = WORKS3_DIR / f"{uni.openalex_id}.parquet"
    meta_path = WORKS3_DIR / f"{uni.openalex_id}.json"
    if path.exists() and meta_path.exists():
        meta = json.loads(meta_path.read_text())
        df = pd.read_parquet(path)
        if meta.get("complete") and len(df) == meta["n_unique"]:
            return df, meta
    rows, expected, got, mtimes = [], {}, {}, []
    for year in range(PANEL_YEAR_MIN, PANEL_YEAR_MAX + 1):
        works, n, mt = _year_pages(uni, year)
        rows += works
        expected[year], got[year] = n, len(works)
        mtimes += mt
    df = pd.DataFrame(rows).drop_duplicates("id")
    df.insert(0, "uni", uni.key)
    short = {y: (expected[y], got[y]) for y in expected if got[y] < expected[y]}
    meta = {"openalex_id": uni.openalex_id, "complete": not short, "incomplete_years": short,
            "n_unique": len(df), "expected_total": sum(expected.values()),
            "extracted_from": datetime.fromtimestamp(min(mtimes), timezone.utc).isoformat(timespec="seconds"),
            "extracted_to": datetime.fromtimestamp(max(mtimes), timezone.utc).isoformat(timespec="seconds")}
    WORKS3_DIR.mkdir(parents=True, exist_ok=True)
    _atomic_parquet(df, path)
    oa.write_json_atomic(meta_path, meta, indent=1)
    return df, meta


def intl_columns(works: pd.DataFrame, home: str) -> pd.DataFrame:
    w = works[~p2._is_excluded(works) & works["year"].between(PANEL_YEAR_MIN, PANEL_YEAR_MAX)]
    rows = []
    for year, g in w.groupby("year"):
        countries = {c for cs in g["countries"] for c in cs if c != home}
        insts = {i for xs in g["partner_institutions"] for i in xs}
        rows.append({"year": int(year), "n_partner_countries": len(countries),
                     "n_intl_works": int((g["n_countries"].fillna(0) >= 2).sum()),
                     "n_partner_institutions": len(insts)})
    return pd.DataFrame(rows)


def check_cache() -> dict:
    """Before building: remove leftover temp files and unreadable cached pages (they are refetched)."""
    tmp = list(oa.HTTP_CACHE_DIR.rglob("*.tmp"))
    for f in tmp:
        f.unlink(missing_ok=True)
    bad = 0
    for f in oa.HTTP_CACHE_DIR.rglob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if "results" in data and "meta" not in data:
                raise ValueError
        except (ValueError, UnicodeDecodeError):
            f.unlink()
            bad += 1
    return {"temp_removed": len(tmp), "unreadable_removed": bad}


def main():
    print("cache check:", check_cache(), flush=True)
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows, sel = [], []
    for uni, role in universities():
        try:
            works, fmeta = fetch(uni)
        except oa.BudgetExhausted as exc:
            print(f"Stopped at {uni.key}: {exc}. Rerun to continue from the cache.")
            oa.log_usage("stage3_panel_partial")
            raise SystemExit(2)
        meta = p2.institution_meta(uni)
        counts = p2.openalex_year_counts(uni)
        r, _, _ = p2.build_university_rows(uni, works, meta, counts)
        panel = pd.DataFrame(r)
        panel = panel[~panel["is_partial"]].merge(intl_columns(works, uni.country), on="year", how="left")
        for c in ("n_partner_countries", "n_intl_works", "n_partner_institutions"):
            panel[c] = panel[c].fillna(0).astype(int)
        panel["role"] = role
        rows.append(panel)
        sel.append({"uni": uni.key, "openalex_id": uni.openalex_id, "name": uni.name, "country": uni.country,
                    "group": uni.group, "role": role, "works_2010_2025": int(panel["works_count"].sum()),
                    "download_complete": fmeta["complete"], "incomplete_years": json.dumps(fmeta["incomplete_years"]),
                    "extracted_from": fmeta["extracted_from"], "extracted_to": fmeta["extracted_to"]})
        print(f"{uni.key:12s} {role:11s} works={len(works):6d} {oa.budget()['credits_used']} credits", flush=True)
    out = pd.concat(rows, ignore_index=True)
    _atomic_parquet(out, PANEL3_PATH)
    pd.DataFrame(sel).to_csv(SELECTION_OUT, index=False)
    META3_PATH.write_text(json.dumps({"extraction_started": started,
                                      "extraction_finished": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                      "source": "OpenAlex API (works, institutions), ROR API",
                                      "note": "OpenAlex changes retroactively; numbers refer to this extraction"},
                                     indent=1))
    print(f"Saved {PANEL3_PATH} {out.shape}", oa.log_usage("stage3_panel"))


if __name__ == "__main__":
    main()
