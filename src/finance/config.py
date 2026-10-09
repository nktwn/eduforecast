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
SIS_ALL_FULLTIME_INSTRUCTIONAL = 1
S_F_TOTAL_FULLTIME_IRPS = 22
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
    files["staff"] = f"S{year}_IS" if year >= HR_RESTRUCTURE_YEAR else f"S{year}_F"
    return files
