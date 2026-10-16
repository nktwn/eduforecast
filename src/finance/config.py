from pathlib import Path

from src.config import BASE_DIR, RESULTS_DIR

FINANCE_DATA_DIR: Path = BASE_DIR / "data" / "finance"
RAW_DIR: Path = FINANCE_DATA_DIR / "raw"
PANEL_PATH: Path = FINANCE_DATA_DIR / "panel.parquet"
INSTITUTIONS_PATH: Path = FINANCE_DATA_DIR / "institutions.parquet"
MANIFEST_PATH: Path = FINANCE_DATA_DIR / "manifest.csv"

FINANCE_RESULTS_DIR: Path = RESULTS_DIR / "finance"
FIG_DIR: Path = BASE_DIR / "docs" / "finance_audit"

for _dir in (RAW_DIR, FINANCE_RESULTS_DIR, FIG_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

IPEDS_DATA_URL = "https://nces.ed.gov/ipeds/datacenter/data/{name}.zip"
CPI_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCNS"
CPI_PATH: Path = RAW_DIR / "CPIAUCNS.csv"

YEAR_MIN = 2010
YEAR_MAX = 2023
YEARS = list(range(YEAR_MIN, YEAR_MAX + 1))

PUBLIC, PRIVATE_NONPROFIT = 1, 2
CONTROLS = (PUBLIC, PRIVATE_NONPROFIT)
ICLEVEL_FOUR_YEAR = 1
HLOFFER_MIN = 7

GR_ADJUSTED_COHORT = 8
GR_BACHELOR_COMPLETERS_150 = 12
EF_ALL_STUDENTS = 1
EAP_FULLTIME_INSTRUCTION_2010 = 2230
EAP_INSTRUCTIONAL_TOTAL = 21000
HR_RESTRUCTURE_YEAR = 2012
FINANCE_FORM_BREAK_FY = 2016


def finance_name(year: int, form: str) -> str:
    return f"F{(year - 1) % 100:02d}{year % 100:02d}_{form}"


def files_for_year(year: int) -> dict[str, str]:
    files = {
        "hd": f"HD{year}",
        "flags": f"FLAGS{year}",
        "ef_a": f"EF{year}A",
        "ef_d": f"EF{year}D",
        "efia": f"EFIA{year}",
        "gr": f"GR{year}",
        "f_gasb": finance_name(year, "F1A"),
        "f_fasb": finance_name(year, "F2"),
    }
    files["eap"] = f"EAP{year}"
    files.update(extra_files_for_year(year))
    return files


ADM_FIRST_YEAR = 2014
SAL_IS_FIRST_YEAR = 2012


def extra_files_for_year(year: int) -> dict[str, str]:
    """Stage-2 components; names checked on the IPEDS Data Center pages for 2010-2023."""
    return {
        "ic": f"IC{year}",
        "ic_ay": f"IC{year}_AY",
        "adm": f"ADM{year}" if year >= ADM_FIRST_YEAR else None,
        "sfa": f"SFA{(year - 1) % 100:02d}{year % 100:02d}",
        "sal": f"SAL{year}_IS" if year >= SAL_IS_FIRST_YEAR else f"SAL{year}_A",
        "c_a": f"C{year}_A",
    }
