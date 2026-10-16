"""Shared helpers for the Academic audit (see ACADEMIC_AUDIT.md).

Conventions (ACADEMIC_AUDIT.md, "Соглашение о неделях"):
- week = ceil(day / 7) clipped to [0, 39], as in notebooks/02_features;
- "week k" = data of weeks 0..k, i.e. days <= 7k (time steps 0..k);
- a registration is "withdrawn by week k" if date_unregistration <= 7k.

The train/test split is the one stored in data/processed/{train,test}_static.csv
(split by student in notebooks/02_features, random_state=42).
"""
from __future__ import annotations

import random
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
RESULTS_DIR = ROOT / "results"
OUT_DIR = RESULTS_DIR / "academic_audit"
# Per-registration predictions: needed by step3, kept out of git (data).
PRED_DIR = OUT_DIR / "predictions"

REG_KEYS = ["id_student", "code_module", "code_presentation"]
TARGET = "is_at_risk"
KS = [5, 10, 20, 39]
SEED = 42
NET_SEEDS = [42, 43, 44]
N_WEEKS = 40
SEQ_FEATS = [
    "weekly_clicks", "is_active", "cumulative_clicks",
    "click_trend", "weeks_since_active",
    "assessment_score", "assessment_submitted",
]


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    try:
        import torch

        torch.manual_seed(seed)
    except ImportError:
        pass


def ensure_dirs() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    PRED_DIR.mkdir(parents=True, exist_ok=True)


def load_raw() -> dict[str, pd.DataFrame]:
    names = ["studentInfo", "studentRegistration", "studentVle",
             "assessments", "studentAssessment"]
    return {n: pd.read_csv(RAW_DIR / f"{n}.csv", na_values=["?"]) for n in names}


# ── static features (notebooks/02_features, cells 7-10) with truncation ──────

def _demographics(si: pd.DataFrame) -> pd.DataFrame:
    si = si.copy()
    si[TARGET] = (si["final_result"] == "Withdrawn").astype(int)
    demo = si[REG_KEYS + [
        "gender", "highest_education", "age_band", "imd_band",
        "disability", "region", "num_of_prev_attempts",
        "studied_credits", TARGET,
    ]].copy()
    demo["gender"] = (demo["gender"] == "M").astype(int)
    demo["disability"] = (demo["disability"] == "Y").astype(int)
    edu_map = {
        "No Formal quals": 0, "Lower Than A Level": 1,
        "A Level or Equivalent": 2, "HE Qualification": 3,
        "Post Graduate Qualification": 4,
    }
    demo["highest_education"] = demo["highest_education"].map(edu_map).fillna(0).astype(int)
    demo["age_band"] = demo["age_band"].map({"0-35": 0, "35-55": 1, "55<=": 2}).fillna(0).astype(int)
    imd_raw = demo["imd_band"].fillna("").str.replace(r"^10-20$", "10-20%", regex=True)
    imd_order = ["0-10%", "10-20%", "20-30%", "30-40%", "40-50%",
                 "50-60%", "60-70%", "70-80%", "80-90%", "90-100%"]
    demo["imd_band"] = imd_raw.map({v: i for i, v in enumerate(imd_order)})
    demo["imd_band"] = demo["imd_band"].fillna(demo["imd_band"].median()).astype(int)
    region = pd.get_dummies(demo["region"], prefix="region", dtype=int)
    return pd.concat([demo.drop(columns="region"), region], axis=1)


def build_static(raw: dict[str, pd.DataFrame], k: int | None) -> pd.DataFrame:
    """Static feature matrix as in 02_features; k=None means the whole course.

    With k: VLE aggregates use weeks <= k only; assessment aggregates use only
    submissions with date_submitted <= 7k. Demographics do not change.
    """
    demo = _demographics(raw["studentInfo"])

    sv = raw["studentVle"].copy()
    sv["week"] = np.ceil(sv["date"] / 7).clip(0, 39).astype(int)
    if k is not None:
        sv = sv[sv["week"] <= k]
    weekly = sv.groupby(REG_KEYS + ["week"])["sum_click"].sum().reset_index(name="weekly_clicks")
    vle = weekly.groupby(REG_KEYS).agg(
        total_clicks=("weekly_clicks", "sum"),
        active_weeks=("week", "nunique"),
        max_weekly_clicks=("weekly_clicks", "max"),
        mean_weekly_clicks=("weekly_clicks", "mean"),
        first_active_week=("week", "min"),
        last_active_week=("week", "max"),
    ).reset_index()
    vle["activity_span"] = vle["last_active_week"] - vle["first_active_week"]
    vle["mean_weekly_clicks"] = vle["mean_weekly_clicks"].round(2)

    ass = raw["assessments"].dropna(subset=["date"])
    sa = raw["studentAssessment"]
    if k is not None:
        sa = sa[sa["date_submitted"] <= 7 * k]
    sa_full = sa.merge(
        ass[["id_assessment", "code_module", "code_presentation", "assessment_type", "date"]],
        on="id_assessment", how="inner",
    )
    sa_full["score"] = sa_full["score"].fillna(0)
    sa_full["is_late"] = (sa_full["date_submitted"] > sa_full["date"]).astype(int)
    agg = sa_full.groupby(REG_KEYS).agg(
        num_assessments_submitted=("id_assessment", "count"),
        mean_score=("score", "mean"),
        num_late_submissions=("is_late", "sum"),
        has_tma=("assessment_type", lambda x: int((x == "TMA").any())),
        has_cma=("assessment_type", lambda x: int((x == "CMA").any())),
    ).reset_index()
    agg["mean_score"] = agg["mean_score"].round(2)

    static = demo.merge(vle, on=REG_KEYS, how="left").merge(agg, on=REG_KEYS, how="left").fillna(0)
    cols = [c for c in static.columns if c != TARGET] + [TARGET]
    return static[cols]


def split_ids() -> tuple[set, set]:
    tr = pd.read_csv(PROCESSED_DIR / "train_static.csv", usecols=["id_student"])
    te = pd.read_csv(PROCESSED_DIR / "test_static.csv", usecols=["id_student"])
    return set(tr["id_student"]), set(te["id_student"])


def feature_cols() -> list[str]:
    cols = pd.read_csv(PROCESSED_DIR / "train_static.csv", nrows=0).columns
    return [c for c in cols if c not in REG_KEYS + [TARGET]]


def unregistration(raw: dict[str, pd.DataFrame]) -> pd.DataFrame:
    return raw["studentRegistration"][REG_KEYS + ["date_unregistration"]]


def still_enrolled(keys: pd.DataFrame, unreg: pd.DataFrame, k: int) -> np.ndarray:
    """Boolean mask aligned with `keys`: not unregistered by the end of week k."""
    m = keys[REG_KEYS].merge(unreg, on=REG_KEYS, how="left")
    assert len(m) == len(keys)
    return ~(m["date_unregistration"] <= 7 * k).to_numpy()


# ── sequential tensors (notebooks/04_lstm, cells 3-6) ─────────────────────────

def load_sequences():
    """Returns X_train_sc, y_train, X_test_sc, y_test, train_keys, test_keys."""
    from sklearn.preprocessing import StandardScaler

    out = []
    for split in ("train", "test"):
        df = pd.read_csv(PROCESSED_DIR / f"{split}_sequential.csv")
        df = df.sort_values(REG_KEYS + ["week"]).reset_index(drop=True)
        n = len(df) // N_WEEKS
        assert (df.iloc[::N_WEEKS]["week"] == 0).all()
        y = df.iloc[::N_WEEKS][TARGET].to_numpy().astype(np.float32)
        keys = df.iloc[::N_WEEKS][REG_KEYS].reset_index(drop=True)
        X = df[SEQ_FEATS].to_numpy().reshape(n, N_WEEKS, len(SEQ_FEATS)).astype(np.float32)
        out.append((X, y, keys))
    (Xtr, ytr, ktr), (Xte, yte, kte) = out
    scaler = StandardScaler()
    nf = len(SEQ_FEATS)
    Xtr_sc = scaler.fit_transform(Xtr.reshape(-1, nf)).reshape(Xtr.shape).astype(np.float32)
    Xte_sc = scaler.transform(Xte.reshape(-1, nf)).reshape(Xte.shape).astype(np.float32)
    return Xtr_sc, ytr, Xte_sc, yte, ktr, kte
