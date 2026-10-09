import argparse
from collections import Counter

import numpy as np
import pandas as pd

from src.research import openalex_client as oa
from src.research.config import (
    PANEL_PATH,
    PANEL_YEAR_MAX,
    PANEL_YEAR_MIN,
    PARTIAL_YEAR,
    RESEARCH_DATA_DIR,
    WORKS_DIR,
)
from src.research.institutions import FOUNDED_FALLBACK, UNI_TYPES, UNIVERSITIES, UNIVERSITY_TYPE_PLACEHOLDER, University

WORK_SELECT = ",".join([
    "id", "publication_year", "type", "fwci", "citation_normalized_percentile",
    "countries_distinct_count", "institutions_distinct_count", "open_access",
    "primary_topic", "authorships", "cited_by_count", "counts_by_year", "is_retracted", "is_paratext",
])
AUTHORSHIPS_CAP = 100
CITATIONS_BY_YEAR_FIRST = 2012
TOP_FIELDS = 5

FIELD_SHARES_PATH = RESEARCH_DATA_DIR / "field_shares.parquet"
PARTNERS_PATH = RESEARCH_DATA_DIR / "partner_countries.parquet"


def _short(openalex_url: str | None) -> str | None:
    return openalex_url.rsplit("/", 1)[-1] if openalex_url else None


def _compact_work(work: dict, inst_id: str) -> dict:
    inst_url = f"https://openalex.org/{inst_id}"
    affiliated, countries = set(), set()
    for a in work.get("authorships") or []:
        countries.update(a.get("countries") or [])
        author_id = _short((a.get("author") or {}).get("id"))
        if author_id is None:
            continue
        for inst in a.get("institutions") or []:
            if inst.get("id") == inst_url or inst_url in (inst.get("lineage") or []):
                affiliated.add(author_id)
                break

    pct = work.get("citation_normalized_percentile") or {}
    topic = work.get("primary_topic") or {}
    oa_info = work.get("open_access") or {}
    return {
        "id": _short(work["id"]),
        "year": work.get("publication_year"),
        "type": work.get("type"),
        "fwci": work.get("fwci"),
        "pct_value": pct.get("value"),
        "top10": pct.get("is_in_top_10_percent"),
        "top1": pct.get("is_in_top_1_percent"),
        "n_countries": work.get("countries_distinct_count"),
        "n_institutions": work.get("institutions_distinct_count"),
        "is_oa": oa_info.get("is_oa"),
        "oa_status": oa_info.get("oa_status"),
        "field": (topic.get("field") or {}).get("display_name"),
        "domain": (topic.get("domain") or {}).get("display_name"),
        "cited_by_count": work.get("cited_by_count"),
        "cites_by_year": [
            {"year": c["year"], "cited_by_count": c["cited_by_count"]}
            for c in work.get("counts_by_year") or []
        ],
        "is_retracted": work.get("is_retracted"),
        "is_paratext": work.get("is_paratext"),
        "n_authorships": len(work.get("authorships") or []),
        "affiliated_authors": sorted(affiliated),
        "countries": sorted(countries),
    }


def _compact_page(inst_id: str):
    def transform(data: dict) -> dict:
        return {"meta": data["meta"], "results": [_compact_work(w, inst_id) for w in data["results"]]}
    return transform


def fetch_works(uni: University, years: range) -> pd.DataFrame:
    rows = []
    for year in years:
        filter_ = f"institutions.id:{uni.openalex_id},publication_year:{year}"
        rows.extend(oa.iter_works(filter_, WORK_SELECT, transform=_compact_page(uni.openalex_id)))
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.drop_duplicates("id")
    df.insert(0, "uni", uni.key)
    return df


def openalex_year_counts(uni: University) -> dict[int, int]:
    groups = oa.group_by(f"institutions.id:{uni.openalex_id}", "publication_year")
    return {int(g["key"]): int(g["count"]) for g in groups}


def institution_meta(uni: University) -> dict:
    inst = oa.fetch_institution(uni.openalex_id)
    try:
        founded = oa.fetch_ror(inst["ror"]).get("established")
    except Exception:
        founded = None
    cby = {c["year"]: c for c in inst.get("counts_by_year", [])}
    return {"inst": inst, "founded": founded, "counts_by_year": cby}


def _aggregate_year(g: pd.DataFrame) -> dict:
    n = len(g)
    known_countries = g["n_countries"].fillna(0) > 0
    fwci = g["fwci"].dropna()
    pct = g["top10"].dropna()
    authors, authors_no_hyper = set(), set()
    for ids, n_auth in zip(g["affiliated_authors"], g["n_authorships"]):
        authors.update(ids)
        if n_auth < AUTHORSHIPS_CAP:
            authors_no_hyper.update(ids)
    return {
        "works_count": n,
        "works_articles_reviews": int(g["type"].isin(["article", "review"]).sum()),
        "intl_collab_share": float((g["n_countries"] > 1).mean()) if n else np.nan,
        "intl_collab_share_known": float((g.loc[known_countries, "n_countries"] > 1).mean()) if known_countries.any() else np.nan,
        "country_unknown_share": float((~known_countries).mean()) if n else np.nan,
        "top10_share": float(pct.astype(bool).mean()) if len(pct) else np.nan,
        "top1_share": float(g["top1"].dropna().astype(bool).mean()) if len(pct) else np.nan,
        "fwci_mean": float(fwci.mean()) if len(fwci) else np.nan,
        "fwci_median": float(fwci.median()) if len(fwci) else np.nan,
        "fwci_coverage": len(fwci) / n if n else np.nan,
        "unique_authors": len(authors),
        "unique_authors_no_hyper": len(authors_no_hyper),
        "oa_share": float(g["is_oa"].fillna(False).astype(bool).mean()) if n else np.nan,
        "truncated_authorships_works": int((g["n_authorships"] >= AUTHORSHIPS_CAP).sum()),
        "works_without_affiliated_author_id": int((g["affiliated_authors"].str.len() == 0).sum()),
        "citations_of_year_works_to_date": int(g["cited_by_count"].fillna(0).sum()),
    }


def _citations_received_by_year(works: pd.DataFrame) -> pd.Series:
    cites = works["cites_by_year"].explode().dropna()
    if cites.empty:
        return pd.Series(dtype=int)
    return pd.DataFrame(cites.tolist()).groupby("year")["cited_by_count"].sum()


def _is_excluded(works: pd.DataFrame) -> pd.Series:
    return works["is_retracted"].fillna(False).astype(bool) | works["is_paratext"].fillna(False).astype(bool)


def build_university_rows(uni: University, all_works: pd.DataFrame, meta: dict, oa_counts: dict[int, int]):
    years = range(PANEL_YEAR_MIN, PARTIAL_YEAR + 1)
    excluded = _is_excluded(all_works)
    excluded_by_year = all_works[excluded].groupby("year").agg(
        retracted=("is_retracted", "sum"), paratext=("is_paratext", "sum"))
    all_by_year = all_works.groupby("year").size()
    works = all_works[~excluded]
    train = works[works["year"].between(PANEL_YEAR_MIN, PANEL_YEAR_MAX)]
    field_totals = train["field"].dropna().value_counts()
    top_fields = list(field_totals.index[:TOP_FIELDS])

    received = _citations_received_by_year(works)

    rows, field_rows, partner_rows = [], [], []
    by_year = {y: g for y, g in works.groupby("year")}
    for year in years:
        g = by_year.get(year, works.iloc[0:0])
        row = {
            "uni": uni.key,
            "name": uni.name,
            "openalex_id": uni.openalex_id,
            "ror": uni.ror,
            "country": uni.country,
            "group": uni.group,
            "founded": meta["founded"] or FOUNDED_FALLBACK.get(uni.key),
            "uni_type": UNI_TYPES.get(uni.key, UNIVERSITY_TYPE_PLACEHOLDER),
            "year": year,
            "is_partial": year == PARTIAL_YEAR,
            **_aggregate_year(g),
        }
        row["works_count_all"] = int(all_by_year.get(year, 0))
        row["retracted_excluded"] = int(excluded_by_year["retracted"].get(year, 0))
        row["paratext_excluded"] = int(excluded_by_year["paratext"].get(year, 0))
        cby = meta["counts_by_year"].get(year, {})
        row["citations_received_in_year"] = (
            int(received.get(year, 0)) if year >= CITATIONS_BY_YEAR_FIRST else np.nan
        )
        row["openalex_inst_cohort_citations"] = cby.get("cited_by_count", np.nan)
        row["openalex_inst_works_count"] = cby.get("works_count", np.nan)
        row["openalex_inst_oa_works_count"] = cby.get("oa_works_count", np.nan)
        row["openalex_groupby_works_count"] = oa_counts.get(year, 0)

        fields = g["field"].dropna().value_counts(normalize=False)
        n = len(g)
        for rank, field in enumerate(top_fields, start=1):
            row[f"field{rank}_name"] = field
            row[f"field{rank}_share"] = fields.get(field, 0) / n if n else np.nan
        for field, count in fields.items():
            field_rows.append({"uni": uni.key, "year": year, "field": field, "works": int(count), "share": count / n})

        partners = Counter()
        for cs in g["countries"]:
            partners.update(c for c in cs if c != uni.country)
        for c, count in partners.items():
            partner_rows.append({"uni": uni.key, "year": year, "partner_country": c, "works": count})
        rows.append(row)
    return rows, field_rows, partner_rows


def build_panel(keys: list[str] | None = None) -> pd.DataFrame:
    unis = [u for u in UNIVERSITIES if keys is None or u.key in keys]
    rows, field_rows, partner_rows = [], [], []
    for uni in unis:
        works_path = WORKS_DIR / f"{uni.key}.parquet"
        if works_path.exists():
            works = pd.read_parquet(works_path)
        else:
            works = fetch_works(uni, range(PANEL_YEAR_MIN, PARTIAL_YEAR + 1))
            works.to_parquet(works_path, index=False)
        meta = institution_meta(uni)
        oa_counts = openalex_year_counts(uni)
        r, f, p = build_university_rows(uni, works, meta, oa_counts)
        rows += r
        field_rows += f
        partner_rows += p
        print(f"{uni.key:10s} works={len(works):6d} budget={oa.budget()}", flush=True)

    panel = pd.DataFrame(rows)
    panel.to_parquet(PANEL_PATH, index=False)
    pd.DataFrame(field_rows).to_parquet(FIELD_SHARES_PATH, index=False)
    pd.DataFrame(partner_rows).to_parquet(PARTNERS_PATH, index=False)
    return panel


def main():
    parser = argparse.ArgumentParser(description="Build the university x year OpenAlex panel")
    parser.add_argument("--only", nargs="*", help="university keys to (re)build")
    args = parser.parse_args()
    try:
        panel = build_panel(args.only)
    except oa.BudgetExhausted as exc:
        print(f"Stopped: {exc}. Cached pages are kept; rerun after the daily reset to continue.")
        raise SystemExit(2)
    print(f"Saved {PANEL_PATH} with shape {panel.shape}")


if __name__ == "__main__":
    main()
