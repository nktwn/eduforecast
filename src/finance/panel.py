import re

import numpy as np
import pandas as pd

from src.finance.config import (
    CONTROLS,
    CPI_PATH,
    YEAR_MAX,
    EF_ALL_STUDENTS,
    GR_ADJUSTED_COHORT,
    GR_BACHELOR_COMPLETERS_150,
    HLOFFER_MIN,
    HR_RESTRUCTURE_YEAR,
    ICLEVEL_FOUR_YEAR,
    INSTITUTIONS_PATH,
    PANEL_PATH,
    EAP_FULLTIME_INSTRUCTION_2010,
    EAP_INSTRUCTIONAL_TOTAL,
    YEARS,
    files_for_year,
)
from src.finance.criterion import COVID_TARGET_YEARS, GASB75_PUBLIC_TARGET_YEAR, MIN_COHORT, PRICE_BASE_FY
from src.finance.download import load

STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI", "ID", "IL", "IN", "IA", "KS", "KY",
    "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH",
    "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
}

CATEGORIES = ["instruction", "research", "public_service", "academic_support", "student_services",
              "institutional_support", "scholarships"]

GASB = {
    "instruction": "F1C011", "research": "F1C021", "public_service": "F1C031", "academic_support": "F1C051",
    "student_services": "F1C061", "institutional_support": "F1C071", "scholarships": "F1C101",
    "auxiliary": "F1C111", "hospital": "F1C121", "independent_ops": "F1C131", "other": "F1C141",
    "total": "F1C191", "om_line": "F1C081",
    "nat_om": ["F1C19OM", "F1C196"], "nat_depreciation": ["F1C19DP", "F1C194"], "nat_interest": ["F1C19IN", "F1C197"],
    "sch_gross": "F1E07", "sch_discounts": "F1E10",
}
FASB = {
    "instruction": "F2E011", "research": "F2E021", "public_service": "F2E031", "academic_support": "F2E041",
    "student_services": "F2E051", "institutional_support": "F2E061", "scholarships": "F2E081",
    "auxiliary": "F2E071", "hospital": "F2E091", "independent_ops": "F2E101", "other": "F2E121",
    "total": "F2E131", "om_line": "F2E111",
    "nat_om": ["F2E134"], "nat_depreciation": ["F2E135"], "nat_interest": ["F2E136"],
    "sch_gross": "F2C07", "sch_discounts": "F2C10",
}
FINANCE_ITEMS = CATEGORIES + ["auxiliary", "hospital", "independent_ops", "other", "total", "om_line"]
NATURAL_ITEMS = ["nat_om", "nat_depreciation", "nat_interest", "sch_gross", "sch_discounts"]

CARNEGIE_GROUPS = {
    15: "R1", 16: "R2", 17: "D/PU",
    18: "Master's L", 19: "Master's M", 20: "Master's S",
    21: "Baccalaureate", 22: "Baccalaureate", 23: "Baccalaureate",
}


def carnegie_group(code) -> str:
    if pd.isna(code) or code < 0:
        return "Unclassified"
    code = int(code)
    if code in CARNEGIE_GROUPS:
        return CARNEGIE_GROUPS[code]
    if 24 <= code <= 32:
        return "Special focus"
    if code == 33:
        return "Tribal"
    return "Other"


def _num(df: pd.DataFrame, col) -> pd.Series:
    cols = col if isinstance(col, list) else [col]
    for c in cols:
        if c in df.columns:
            return pd.to_numeric(df[c], errors="coerce")
    return pd.Series(np.nan, index=df.index)


def _finance(year: int, files: dict) -> pd.DataFrame:
    frames = []
    for form, name, mapping in (("GASB", files["f_gasb"], GASB), ("FASB", files["f_fasb"], FASB)):
        df = load(name)
        if df is None:
            continue
        out = pd.DataFrame({"UNITID": df["UNITID"]})
        for item in FINANCE_ITEMS + NATURAL_ITEMS:
            out[f"exp_{item}"] = _num(df, mapping[item])
        if form == "FASB" and "F2C10" not in df.columns:
            out["exp_sch_discounts"] = _num(df, "F2C08") + _num(df, "F2C09").fillna(0)
        out["finance_form"] = form
        frames.append(out)
    fin = pd.concat(frames, ignore_index=True)
    fin["finance_in_both_forms"] = fin.duplicated("UNITID", keep=False)
    return fin.drop_duplicates("UNITID", keep="first")


def _hd(files: dict) -> pd.DataFrame:
    cols = ["UNITID", "INSTNM", "STABBR", "ICLEVEL", "CONTROL", "HLOFFER", "DEGGRANT", "C21BASIC", "C18BASIC",
            "C15BASIC", "CCBASIC", "NEWID", "DEATHYR", "CLOSEDAT", "CYACTIVE", "F1SYSTYP"]
    return load(files["hd"], cols)


def _flags(files: dict) -> pd.DataFrame:
    df = load(files["flags"], ["UNITID", "PRCH_F", "IDX_F", "PRCH_EF", "PRCH_GR", "PRCH_HR"])
    if df is None:
        return pd.DataFrame(columns=["UNITID"])
    for c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def _enrollment(files: dict) -> pd.DataFrame:
    ef = load(files["ef_a"], ["UNITID", "EFALEVEL", "LINE", "EFTOTLT"])
    ef = ef[ef["EFALEVEL"] == EF_ALL_STUDENTS].drop_duplicates("UNITID")
    out = ef[["UNITID"]].assign(fall_enrollment=pd.to_numeric(ef["EFTOTLT"], errors="coerce"))
    efia = load(files["efia"], ["UNITID", "FTEUG", "FTEGD", "FTEDPP", "EFTEUG", "EFTEGD"])
    for c in ("FTEUG", "FTEGD", "FTEDPP", "EFTEUG", "EFTEGD"):
        if c not in efia.columns:
            efia[c] = np.nan
        efia[c] = pd.to_numeric(efia[c], errors="coerce")
    fte = efia[["UNITID"]].assign(
        fte_ug=efia["FTEUG"], fte_grad=efia["FTEGD"], fte_dpp=efia["FTEDPP"],
        fte_total=efia[["FTEUG", "FTEGD", "FTEDPP"]].sum(axis=1, min_count=1),
    )
    return out.merge(fte, on="UNITID", how="outer")


def _retention(files: dict) -> pd.DataFrame:
    d = load(files["ef_d"], ["UNITID", "RET_PCF", "RRFTCTA", "STUFACR"])
    return pd.DataFrame({"UNITID": d["UNITID"], "retention_rate": pd.to_numeric(d["RET_PCF"], errors="coerce"),
                         "retention_cohort": pd.to_numeric(d.get("RRFTCTA"), errors="coerce"),
                         "student_faculty_ratio": pd.to_numeric(d.get("STUFACR"), errors="coerce")})


def _graduation(files: dict) -> pd.DataFrame:
    gr = load(files["gr"], ["UNITID", "GRTYPE", "GRTOTLT"])
    gr["GRTOTLT"] = pd.to_numeric(gr["GRTOTLT"], errors="coerce")
    wide = gr[gr["GRTYPE"].isin([GR_ADJUSTED_COHORT, GR_BACHELOR_COMPLETERS_150])].pivot_table(
        index="UNITID", columns="GRTYPE", values="GRTOTLT", aggfunc="sum")
    cohort = wide.get(GR_ADJUSTED_COHORT)
    completers = wide.get(GR_BACHELOR_COMPLETERS_150)
    rate = (completers / cohort.where(cohort > 0)) * 100
    return pd.DataFrame({"grad_cohort": cohort, "grad_rate_150": rate}).reset_index()


def _faculty(year: int, files: dict) -> pd.DataFrame:
    eap = load(files["eap"])
    if eap is None:
        return pd.DataFrame(columns=["UNITID"])
    if year >= HR_RESTRUCTURE_YEAR:
        sub = eap[eap["EAPCAT"] == EAP_INSTRUCTIONAL_TOTAL]
        value = sub["EAPFT"]
    else:
        sub = eap[eap["EAPRECTP"] == EAP_FULLTIME_INSTRUCTION_2010]
        value = sub["EAPTOT"]
    return pd.DataFrame({"UNITID": sub["UNITID"], "faculty_ft_instructional": pd.to_numeric(value, errors="coerce")})


def build_year(year: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    files = files_for_year(year)
    hd = _hd(files)
    flags = _flags(files)
    enroll = _enrollment(files)
    fin = _finance(year, files)

    child_fte = (flags[flags.get("PRCH_F", pd.Series(dtype=float)) == 2][["UNITID", "IDX_F"]]
                 .merge(enroll[["UNITID", "fte_total"]], on="UNITID", how="left")
                 .groupby("IDX_F")["fte_total"].sum().rename("child_fte_with_finance"))

    df = (hd.merge(flags, on="UNITID", how="left")
          .merge(enroll, on="UNITID", how="left")
          .merge(_retention(files), on="UNITID", how="left")
          .merge(_graduation(files), on="UNITID", how="left")
          .merge(_faculty(year, files), on="UNITID", how="left")
          .merge(fin, on="UNITID", how="left")
          .merge(child_fte, left_on="UNITID", right_index=True, how="left"))
    df.insert(1, "year", year)

    in_scope = (
        (df["ICLEVEL"] == ICLEVEL_FOUR_YEAR) & df["CONTROL"].isin(CONTROLS) & (df["HLOFFER"] >= HLOFFER_MIN)
        & (df["DEGGRANT"] == 1) & df["STABBR"].isin(STATES)
    )
    return df[in_scope].copy(), hd.assign(year=year)


def finalize(panel: pd.DataFrame) -> pd.DataFrame:
    p = panel.rename(columns={"UNITID": "unitid", "INSTNM": "name", "STABBR": "state", "CONTROL": "control",
                              "ICLEVEL": "iclevel", "HLOFFER": "hloffer", "PRCH_F": "prch_f", "IDX_F": "idx_f"})
    p["control_label"] = p["control"].map({1: "public", 2: "private_nonprofit"})
    schemes = ["C21BASIC", "C18BASIC", "C15BASIC", "CCBASIC"]
    for c in schemes:
        if c not in p.columns:
            p[c] = np.nan
        p[c] = pd.to_numeric(p[c], errors="coerce").where(lambda s: s > 0)
    latest = p.sort_values("year").groupby("unitid")[schemes].last()
    carnegie = latest["C21BASIC"]
    for c in schemes[1:]:
        carnegie = carnegie.fillna(latest[c])
    p["carnegie_basic_2021"] = p["unitid"].map(carnegie)
    p["carnegie_group"] = p["carnegie_basic_2021"].map(carnegie_group)
    p["peer_group"] = p["control_label"] + " | " + p["carnegie_group"]

    p["finance_child"] = p["prch_f"].isin([2])
    p["finance_partial"] = p["prch_f"].isin([3, 5, 6])
    p["fte_finance_basis"] = p["fte_total"] + p["child_fte_with_finance"].fillna(0)
    p.loc[p["finance_child"], [f"exp_{c}" for c in FINANCE_ITEMS + NATURAL_ITEMS]] = np.nan

    p["exp_core_total"] = p[[f"exp_{c}" for c in CATEGORIES]].sum(axis=1, min_count=len(CATEGORIES))
    valid_fte = p["fte_finance_basis"].where(p["fte_finance_basis"] > 0)
    valid_total = p["exp_total"].where(p["exp_total"] > 0)
    for c in CATEGORIES + ["total", "core_total"]:
        p[f"{c}_per_fte"] = p[f"exp_{c}"] / valid_fte
    for c in CATEGORIES:
        p[f"{c}_share"] = p[f"exp_{c}"] / valid_total
    p["exp_total_with_discounts"] = p["exp_total"] + p["exp_sch_discounts"].fillna(0)
    p["sch_gross_per_fte"] = p["exp_sch_gross"] / valid_fte
    p["sch_gross_share_of_total_with_discounts"] = p["exp_sch_gross"] / p["exp_total_with_discounts"].where(
        p["exp_total_with_discounts"] > 0)
    deflator = p["year"].map(cpi_deflator())
    for c in CATEGORIES + ["total", "core_total"]:
        p[f"{c}_per_fte_real"] = p[f"{c}_per_fte"] * deflator
    p["exp_core_total_real"] = p["exp_core_total"] * deflator
    p["sch_gross_per_fte_real"] = p["sch_gross_per_fte"] * deflator
    p["cpi_deflator_to_fy_base"] = deflator

    has_bachelor = p.groupby("unitid")["grad_cohort"].transform(lambda s: (s > 0).any())
    p["has_bachelor_cohort"] = has_bachelor
    p["eligible_retention"] = has_bachelor & (p["retention_cohort"] >= MIN_COHORT)
    p["eligible_grad"] = p["grad_cohort"] >= MIN_COHORT
    p["flag_covid"] = p["year"].isin(COVID_TARGET_YEARS)
    p["flag_gasb75"] = (p["control"] == 1) & (p["year"] == GASB75_PUBLIC_TARGET_YEAR)
    p["fte_per_faculty"] = p["fte_total"] / p["faculty_ft_instructional"].where(p["faculty_ft_instructional"] > 0)
    keep = [c for c in p.columns if not c.startswith(("C21", "C18", "C15", "CC", "PRCH_", "DEGGRANT"))]
    return p[keep].sort_values(["unitid", "year"]).reset_index(drop=True)


def cpi_deflator() -> dict[int, float]:
    cpi = pd.read_csv(CPI_PATH)
    cpi.columns = ["date", "cpi"]
    cpi["date"] = pd.to_datetime(cpi["date"])
    cpi["fy"] = cpi["date"].dt.year + (cpi["date"].dt.month >= 7).astype(int)
    fy = cpi.groupby("fy")["cpi"].agg(["mean", "size"])
    fy = fy[fy["size"] == 12]["mean"]
    return (fy[PRICE_BASE_FY] / fy).to_dict()


SAME_ENTITY_SIMILARITY = 0.5
STOP_WORDS = {"the", "of", "university", "college", "inc", "main", "campus", "and", "at", "school", "state"}


def name_similarity(a: str, b: str) -> float:
    def tokens(x):
        return {t for t in re.findall(r"[a-z]+", str(x).lower()) if t not in STOP_WORDS}
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return float(str(a).lower().split("-")[0].strip() == str(b).lower().split("-")[0].strip())
    return len(ta & tb) / len(ta | tb)


def splice_series(p: pd.DataFrame, hd: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    first = p.groupby("unitid")["year"].min()
    last = p.groupby("unitid")["year"].max()
    names = p.groupby("unitid")["name"].last()
    hd = hd.assign(NEWID=pd.to_numeric(hd["NEWID"], errors="coerce"))
    links = []
    for unitid, last_year in last[last < YEAR_MAX].items():
        rows = hd[(hd["UNITID"] == unitid) & (hd["year"] >= last_year) & (hd["NEWID"] > 0)].sort_values("year")
        if not rows.empty:
            links.append((unitid, int(rows["NEWID"].iloc[0]), last_year))
    n_predecessors = pd.Series([b for _, b, _ in links]).value_counts().to_dict()

    successor_of, superseded_from, flags, events = {}, {}, {}, []
    for a, b, last_year in links:
        event = {"unitid": a, "name": names[a], "newid": b, "last_year": last_year}
        if b not in first.index or b == a:
            events.append({**event, "type": "merged_outside_panel"})
            continue
        similarity = name_similarity(names[a], names[b])
        event.update({"new_name": names[b], "name_similarity": round(similarity, 2)})
        new_successor = first[b] >= last_year
        if new_successor and n_predecessors[b] == 1:
            successor_of[b] = a
            superseded_from[a] = first[b]
            flags[(b, first[b])] = "id_transition"
            kind = "spliced_id_change"
        elif new_successor:
            flags[(b, first[b])] = "id_transition"
            kind = "merger_new_entity_cut"
        elif similarity >= SAME_ENTITY_SIMILARITY:
            flags[(b, last_year + 1)] = "id_transition"
            kind = "reporting_change_cut"
        else:
            flags[(b, last_year + 1)] = "merger_absorption"
            kind = "real_merger_cut"
        events.append({**event, "type": kind})

    def root(u):
        seen = set()
        while u in successor_of and u not in seen:
            seen.add(u)
            u = successor_of[u]
        return u

    p["superseded"] = p["unitid"].map(superseded_from).le(p["year"]).fillna(False).astype(bool)
    p["series_id"] = np.where(p["superseded"], p["unitid"], p["unitid"].map(root))
    key = list(zip(p["unitid"], p["year"]))
    p["id_transition"] = [flags.get(k) == "id_transition" for k in key]
    p["merger_absorption"] = [flags.get(k) == "merger_absorption" for k in key]
    return p, pd.DataFrame(events)


def main():
    panels, hds = [], []
    for year in YEARS:
        part, hd = build_year(year)
        panels.append(part)
        hds.append(hd)
        print(year, len(part), flush=True)
    hd_all = pd.concat(hds, ignore_index=True)
    panel, events = splice_series(finalize(pd.concat(panels, ignore_index=True)), hd_all)
    panel.to_parquet(PANEL_PATH, index=False)
    hd_all.to_parquet(INSTITUTIONS_PATH, index=False)
    events.to_csv(PANEL_PATH.parent / "id_events.csv", index=False)
    print(f"Saved {PANEL_PATH} {panel.shape}")


if __name__ == "__main__":
    main()
