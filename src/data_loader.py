"""Functions to load OULAD CSV tables from data/raw/."""

from pathlib import Path
from typing import Optional

import pandas as pd

from .config import RAW_DIR


class DataLoader:
    """Loads the seven OULAD CSV files from *raw_dir*.

    Parameters
    ----------
    raw_dir:
        Directory that contains the OULAD CSV files.
        Defaults to the path defined in ``config.RAW_DIR``.
    """

    def __init__(self, raw_dir: Optional[Path] = None) -> None:
        self.raw_dir = Path(raw_dir) if raw_dir else RAW_DIR

    def _load(self, filename: str) -> pd.DataFrame:
        path = self.raw_dir / filename
        if not path.exists():
            raise FileNotFoundError(
                f"{filename} not found in {self.raw_dir}. "
                "See data/README.md for download instructions."
            )
        df = pd.read_csv(path)
        print(f"Loaded {filename}: {df.shape[0]:,} rows × {df.shape[1]} cols")
        return df

    def load_student_info(self) -> pd.DataFrame:
        """Load studentInfo.csv — one row per (student, module, presentation)."""
        return self._load("studentInfo.csv")

    def load_student_registration(self) -> pd.DataFrame:
        """Load studentRegistration.csv — registration / unregistration dates."""
        return self._load("studentRegistration.csv")

    def load_student_vle(self) -> pd.DataFrame:
        """Load studentVle.csv — daily click counts per VLE resource."""
        return self._load("studentVle.csv")

    def load_assessments(self) -> pd.DataFrame:
        """Load assessments.csv — assessment metadata (type, weight, due date)."""
        return self._load("assessments.csv")

    def load_student_assessment(self) -> pd.DataFrame:
        """Load studentAssessment.csv — per-student assessment scores."""
        return self._load("studentAssessment.csv")

    def load_courses(self) -> pd.DataFrame:
        """Load courses.csv — module and presentation metadata."""
        return self._load("courses.csv")

    def load_vle(self) -> pd.DataFrame:
        """Load vle.csv — VLE resource metadata (type, week_from, week_to)."""
        return self._load("vle.csv")

    def load_all(self) -> dict[str, pd.DataFrame]:
        """Load all seven OULAD tables and return them in a named dict.

        Returns
        -------
        dict with keys:
            ``student_info``, ``student_registration``, ``student_vle``,
            ``assessments``, ``student_assessment``, ``courses``, ``vle``
        """
        print("=" * 50)
        print("Loading OULAD dataset tables")
        print("=" * 50)

        tables = {
            "student_info": self.load_student_info(),
            "student_registration": self.load_student_registration(),
            "student_vle": self.load_student_vle(),
            "assessments": self.load_assessments(),
            "student_assessment": self.load_student_assessment(),
            "courses": self.load_courses(),
            "vle": self.load_vle(),
        }

        print("-" * 50)
        print(f"Total tables loaded: {len(tables)}")
        total_rows = sum(df.shape[0] for df in tables.values())
        print(f"Total rows across all tables: {total_rows:,}")
        print("=" * 50)
        return tables
