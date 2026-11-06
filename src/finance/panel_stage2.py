"""Stage-2 panel: the F1 panel plus admissions, aid, prices, staff, enrollment mix,
programme mix and natural expense classes.

The F1 panel (data/finance/panel.parquet) is not modified; new columns are joined on
(unitid, year) and written to data/finance/panel_stage2.parquet.

Year convention as in F1 (FINANCE_DATA_AUDIT.md §1): panel year Y = IPEDS collection
year Y. Files per year are listed in config.extra_files_for_year.

  python -m src.finance.panel_stage2
"""
import re

import numpy as np
import pandas as pd

from src.finance.config import (
    ADM_FIRST_YEAR,
    FINANCE_DATA_DIR,
    HR_RESTRUCTURE_YEAR,
    PANEL_PATH,
    RAW_DIR,
    SAL_IS_FIRST_YEAR,
    YEARS,
    files_for_year,
)
from src.finance.panel import CATEGORIES, cpi_deflator

PANEL2_PATH = FINANCE_DATA_DIR / "panel_stage2.parquet"
COVERAGE_PATH = FINANCE_DATA_DIR / "stage2_component_coverage.csv"

EF_FULL_TIME, EF_PART_TIME, EF_GRADUATE, EF_ALL = 21, 41, 12, 1
EAP_INSTRUCTIONAL_STAFF = 21000
ARANK_ALL = 7
AWLEVEL_BACHELOR = 5

# Natural expense classes (IPEDS dictionaries, F1A part C line 19 / F2 part E line 13).
NATURAL = {
    "GASB": {"salaries": "F1C192", "benefits": "F1C193", "om": ["F1C19OM", "F1C196"],
             "depreciation": ["F1C19DP", "F1C194"], "interest": ["F1C19IN", "F1C197"],
             "other": ["F1C19OT", "F1C195"], "total": "F1C191"},
    "FASB": {"salaries": "F2E132", "benefits": "F2E133", "om": "F2E134", "depreciation": "F2E135",
             "interest": "F2E136", "other": "F2E137", "total": "F2E131"},
}
NATURAL_CLASSES = ["salaries", "benefits", "om", "depreciation", "interest", "other"]
NATURAL_OM_FIRST_YEAR = 2016
SHARE_BOUNDS = (-1.0, 2.0)

# Two-digit CIP groups (CIP 2010/2020 families). STEM is the narrow definition below.
CIP_GROUPS = {
    "computer_science": [11],
    "engineering": [14, 15],
    "math_physical_bio": [26, 27, 40, 41],
    "health": [51],
    "business": [52],
    "education": [13],
    "law": [22],
    "social_behavioral": [42, 45],
    "humanities_arts": [16, 23, 24, 38, 50, 54],
}
STEM_CIP2 = [11, 14, 15, 26, 27, 40, 41]


def load(name: str, usecols=None) -> pd.DataFrame | None:
    """Like download.load, but rows with a trailing comma (e.g. IC2010_AY) do not shift columns."""
    path = RAW_DIR / f"{name}.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path, encoding="latin-1", low_memory=False, index_col=False)
    df.columns = [re.sub(r"^[^A-Za-z0-9_]+", "", c.replace("ï»¿", "")).strip().upper() for c in df.columns]
    if usecols is not None:
        df = df[[c for c in usecols if c in df.columns]]
    return df


def _num(df: pd.DataFrame, col) -> pd.Series:
    for c in (col if isinstance(col, list) else [col]):
        if c in df.columns:
            return pd.to_numeric(df[c], errors="coerce")
    return pd.Series(np.nan, index=df.index)


def _admissions(year: int, files: dict) -> pd.DataFrame:
    df = load(files["adm"] if year >= ADM_FIRST_YEAR else files["ic"], ["UNITID", "APPLCN", "ADMSSN", "ENRLT"])
    out = pd.DataFrame({"UNITID": df["UNITID"], "applicants": _num(df, "APPLCN"), "admitted": _num(df, "ADMSSN"),
                        "enrolled_first_time": _num(df, "ENRLT")})
    out["admit_rate"] = out["admitted"] / out["applicants"].where(out["applicants"] > 0)
    out["yield_rate"] = out["enrolled_first_time"] / out["admitted"].where(out["admitted"] > 0)
    return out


def _prices(files: dict) -> pd.DataFrame:
    df = load(files["ic_ay"], ["UNITID", "CHG2AY3", "CHG3AY3", "CHG5AY3"])
    return pd.DataFrame({"UNITID": df["UNITID"], "tuition_fees_instate": _num(df, "CHG2AY3"),
                         "tuition_fees_outstate": _num(df, "CHG3AY3"), "room_board_oncampus": _num(df, "CHG5AY3")})


def _aid(files: dict) -> pd.DataFrame:
    df = load(files["sfa"], ["UNITID", "UPGRNTP", "PGRNT_P", "IGRNT_P", "NPIST2", "NPGRN2"])
    return pd.DataFrame({"UNITID": df["UNITID"], "pell_share_ug": _num(df, "UPGRNTP") / 100,
                         "pell_share_ftft": _num(df, "PGRNT_P") / 100,
                         "inst_aid_share_ftft": _num(df, "IGRNT_P") / 100,
                         "net_price_public": _num(df, "NPIST2"), "net_price_private": _num(df, "NPGRN2")})


def _salaries(year: int, files: dict) -> pd.DataFrame:
    if year < SAL_IS_FIRST_YEAR:
        return pd.DataFrame(columns=["UNITID"])
    df = load(files["sal"], ["UNITID", "ARANK", "SAEQ9AT", "SAAVMNT", "SATOTLT"])
    df = df[pd.to_numeric(df["ARANK"], errors="coerce") == ARANK_ALL]
    # 2012-2015 report only the average monthly salary, 2017+ only the equated 9-month salary;
    # in 2016 both exist and SAEQ9AT / (9 * SAAVMNT) has median 1.0000 (94% within 1%).
    salary = _num(df, "SAEQ9AT").fillna(9 * _num(df, "SAAVMNT"))
    return pd.DataFrame({"UNITID": df["UNITID"], "faculty_avg_salary_9mo": salary,
                         "faculty_salary_count": _num(df, "SATOTLT")}).drop_duplicates("UNITID")


def _staff(year: int, files: dict) -> pd.DataFrame:
    if year < HR_RESTRUCTURE_YEAR:
        return pd.DataFrame(columns=["UNITID"])
    df = load(files["eap"], ["UNITID", "EAPCAT", "EAPTOT", "EAPFT", "EAPPT"])
    df = df[pd.to_numeric(df["EAPCAT"], errors="coerce") == EAP_INSTRUCTIONAL_STAFF].drop_duplicates("UNITID")
    tot = _num(df, "EAPTOT")
    return pd.DataFrame({"UNITID": df["UNITID"], "instr_staff_total": tot,
                         "ft_instr_staff_share": _num(df, "EAPFT") / tot.where(tot > 0)})


def _enrollment_mix(files: dict) -> pd.DataFrame:
    ef = load(files["ef_a"], ["UNITID", "EFALEVEL", "EFTOTLT"])
    ef["EFTOTLT"] = pd.to_numeric(ef["EFTOTLT"], errors="coerce")
    wide = ef[ef["EFALEVEL"].isin([EF_ALL, EF_FULL_TIME, EF_PART_TIME, EF_GRADUATE])].pivot_table(
        index="UNITID", columns="EFALEVEL", values="EFTOTLT", aggfunc="first")
    total = wide.get(EF_ALL).where(wide.get(EF_ALL) > 0)
    return pd.DataFrame({"full_time_share": wide.get(EF_FULL_TIME) / total,
                         "part_time_share": wide.get(EF_PART_TIME) / total,
                         "graduate_share": wide.get(EF_GRADUATE) / total}).reset_index()


def _programme_mix(files: dict) -> pd.DataFrame:
    path = RAW_DIR / f"{files['c_a']}.csv"
    df = pd.read_csv(path, encoding="latin-1", index_col=False, dtype={"CIPCODE": str}, low_memory=False)
    df.columns = [re.sub(r"^[^A-Za-z0-9_]+", "", c.replace("ï»¿", "")).strip().upper() for c in df.columns]
    six_digit = df["CIPCODE"].str.fullmatch(r"\d{2}\.\d{4}")
    df = df[six_digit & (pd.to_numeric(df["MAJORNUM"]) == 1) & (pd.to_numeric(df["AWLEVEL"]) == AWLEVEL_BACHELOR)]
    df = df.assign(cip2=df["CIPCODE"].str[:2].astype(int), n=pd.to_numeric(df["CTOTALT"], errors="coerce"))
    total = df.groupby("UNITID")["n"].sum()
    out = pd.DataFrame({"bachelor_degrees": total})
    valid = total.where(total > 0)
    for name, codes in CIP_GROUPS.items():
        out[f"deg_share_{name}"] = df[df["cip2"].isin(codes)].groupby("UNITID")["n"].sum().reindex(
            total.index, fill_value=0) / valid
    out["deg_share_stem"] = df[df["cip2"].isin(STEM_CIP2)].groupby("UNITID")["n"].sum().reindex(
        total.index, fill_value=0) / valid
    return out.reset_index()


def _natural(files: dict) -> pd.DataFrame:
    frames = []
    for form, key in (("GASB", "f_gasb"), ("FASB", "f_fasb")):
        df = load(files[key])
        if df is None:
            continue
        out = pd.DataFrame({"UNITID": df["UNITID"]})
        for cls in NATURAL_CLASSES + ["total"]:
            out[f"nat_{cls}"] = _num(df, NATURAL[form][cls])
        out["_form"] = form
        frames.append(out)
    return pd.concat(frames, ignore_index=True).drop_duplicates("UNITID", keep="first")


COMPONENTS = {
    "adm": lambda y, f: _admissions(y, f),
    "ic_ay": lambda y, f: _prices(f),
    "sfa": lambda y, f: _aid(f),
    "sal": lambda y, f: _salaries(y, f),
    "eap_staff": lambda y, f: _staff(y, f),
    "ef_mix": lambda y, f: _enrollment_mix(f),
    "c_a": lambda y, f: _programme_mix(f),
    "natural": lambda y, f: _natural(f),
}


def build_year(year: int) -> tuple[pd.DataFrame, list[dict]]:
    files = files_for_year(year)
    merged, coverage = None, []
    for name, fn in COMPONENTS.items():
        part = fn(year, files)
        coverage.append({"year": year, "component": name, "rows_in_file": len(part)})
        part = part.drop_duplicates("UNITID").astype({"UNITID": "int64"})
        merged = part if merged is None else merged.merge(part, on="UNITID", how="outer")
    return merged.assign(year=year).rename(columns={"UNITID": "unitid"}), coverage


def derive(p: pd.DataFrame) -> pd.DataFrame:
    """Harmonize and derive features; money in FY2023 dollars (CPI-U, as in F1)."""
    p["net_price"] = np.where(p["control"] == 1, p["net_price_public"], p["net_price_private"])
    p.loc[p["finance_child"], [f"nat_{c}" for c in NATURAL_CLASSES + ["total"]]] = np.nan
    # O&M is a separate natural class only from FY2016 (both forms report 0 before: it is spread
    # over the other natural classes), so salaries/other shares have a small break at 2016.
    p.loc[p["year"] < NATURAL_OM_FIRST_YEAR, "nat_om"] = np.nan
    total = p["nat_total"].where(p["nat_total"] > 0)
    for c in NATURAL_CLASSES:
        p[f"nat_{c}_share"] = p[f"nat_{c}"] / total
    # GASB reported O&M as a natural class only from FY2015; before, it sits in "all other".
    p["nat_other_incl_om"] = p["nat_other"] + p["nat_om"].fillna(0)
    p["nat_other_incl_om_share"] = p["nat_other_incl_om"] / total
    p["nat_om_reported_separately"] = p["nat_om"].notna()
    p["nat_compensation_share"] = (p["nat_salaries"] + p["nat_benefits"]) / total

    deflator = p["year"].map(cpi_deflator())
    for c in ["tuition_fees_instate", "tuition_fees_outstate", "room_board_oncampus", "net_price"]:
        p[f"{c}_real"] = p[c] * deflator
    p["faculty_avg_salary_9mo_real"] = p["faculty_avg_salary_9mo"] * deflator
    valid_fte = p["fte_finance_basis"].where(p["fte_finance_basis"] > 0)
    for c in ["salaries", "benefits", "depreciation", "interest"]:
        p[f"nat_{c}_per_fte_real"] = p[f"nat_{c}"] / valid_fte * deflator
    p["core_share_of_total"] = p["exp_core_total"] / p["exp_total"].where(p["exp_total"] > 0)
    core = p["exp_core_total"].where(p["exp_core_total"] > 0)
    for c in CATEGORIES:
        p[f"{c}_share_core"] = p[f"exp_{c}"] / core

    # Outlier rule (FINANCE_DATA_AUDIT.md §15): an accounting share outside [-1, 2] is a reporting
    # artefact (system offices, negative totals); the share is set to NaN, source amounts are kept.
    shares = [f"nat_{c}_share" for c in NATURAL_CLASSES] + ["nat_other_incl_om_share", "nat_compensation_share",
                                                             "core_share_of_total"] + [f"{c}_share_core" for c in
                                                                                       CATEGORIES]
    bad = (p[shares] < SHARE_BOUNDS[0]) | (p[shares] > SHARE_BOUNDS[1])
    p["share_outlier_nulled"] = bad.any(axis=1)
    p[shares] = p[shares].mask(bad)
    return p


def main():
    panel = pd.read_parquet(PANEL_PATH)
    parts, coverage = [], []
    for year in YEARS:
        part, cov = build_year(year)
        parts.append(part)
        coverage += cov
        print(year, len(part), flush=True)
    extra = pd.concat(parts, ignore_index=True)
    overlap = [c for c in extra.columns if c in panel.columns and c not in ("unitid", "year")]
    assert not overlap, overlap
    p = derive(panel.merge(extra, on=["unitid", "year"], how="left"))
    assert len(p) == len(panel)
    p.to_parquet(PANEL2_PATH, index=False)
    pd.DataFrame(coverage).to_csv(COVERAGE_PATH, index=False)
    print(f"Saved {PANEL2_PATH} {p.shape}")


if __name__ == "__main__":
    main()
