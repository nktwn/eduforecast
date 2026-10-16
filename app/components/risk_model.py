"""Early-warning dropout risk model for the Academic pages (pure functions, no Streamlit).

Scheme (see ACADEMIC_AUDIT.md):
- features use only data up to the end of week k (days <= 7k): VLE clicks with
  date <= 7k and assessments with date_submitted <= 7k, plus registration-time
  demographics;
- the population at week k is the registrations not unregistered by day 7k;
- one random forest is pooled over all modules (module indicators are features),
  results are shown per module;
- every risk is out-of-sample: GroupKFold by student, so a student's risk comes
  from a model that never saw that student;
- the target is final_result == "Withdrawn".
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.model_selection import GroupKFold

K_OPTIONS = (5, 10, 20)
DEFAULT_K = 5
TOP_SHARE, MID_SHARE = 0.10, 0.20  # risk groups: top 10%, next 20%, rest
N_SPLITS = 5
SEED = 42
REG_KEYS = ["id_student", "code_module", "code_presentation"]
MODULES = ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG"]

# Student-level features: candidates for the "main reason".
STUDENT_FEATURES = [
    "total_clicks", "active_days", "clicks_last_2w", "assessments_submitted",
    "avg_score", "min_score", "num_of_prev_attempts", "studied_credits",
    "edu_level", "imd_level", "age_level",
]
# Context features (course, presentation): used by the model, never shown as a reason.
CONTEXT_FEATURES = [f"module_{m}" for m in MODULES] + ["presentation_J"]
FEATURES = STUDENT_FEATURES + CONTEXT_FEATURES
FEATURE_LABELS = {
    "total_clicks": "Активность в LMS",
    "active_days": "Активные дни в LMS",
    "clicks_last_2w": "Активность за последние 2 недели",
    "assessments_submitted": "Сданные задания",
    "avg_score": "Средний балл",
    "min_score": "Минимальный балл",
    "num_of_prev_attempts": "Повторные попытки",
    "studied_credits": "Учебная нагрузка (кредиты)",
    "edu_level": "Уровень образования",
    "imd_level": "Социально-экономический индекс",
    "age_level": "Возрастная группа",
}
NO_RISK_FACTOR = "Нет выраженных факторов риска"

_EDU = {"No Formal quals": 0, "Lower Than A Level": 1, "A Level or Equivalent": 2,
        "HE Qualification": 3, "Post Graduate Qualification": 4}
_AGE = {"0-35": 0, "35-55": 1, "55<=": 2}
_IMD = {b: i for i, b in enumerate(["0-10%", "10-20%", "20-30%", "30-40%", "40-50%",
                                    "50-60%", "60-70%", "70-80%", "80-90%", "90-100%"])}


def build_features(info: pd.DataFrame, vle: pd.DataFrame, student_assessment: pd.DataFrame,
                   assessments: pd.DataFrame, registration: pd.DataFrame, k: int) -> pd.DataFrame:
    """One row per registration (all modules); features use days <= 7k only.

    Adds `enrolled_at_k` (not unregistered by day 7k) and `is_withdrawn` (target).
    """
    cutoff = 7 * k
    df = info.copy()

    v = vle.loc[vle["date"] <= cutoff]
    vle_f = v.groupby(REG_KEYS).agg(total_clicks=("sum_click", "sum"),
                                    active_days=("date", "nunique")).reset_index()
    recent = v.loc[v["date"] > cutoff - 14].groupby(REG_KEYS)["sum_click"].sum()
    vle_f = vle_f.merge(recent.rename("clicks_last_2w").reset_index(), on=REG_KEYS, how="left")

    a = assessments[["id_assessment", "code_module", "code_presentation"]]
    sa = student_assessment.loc[student_assessment["date_submitted"] <= cutoff]
    sa = sa.merge(a, on="id_assessment", how="inner")
    sa_f = sa.groupby(REG_KEYS).agg(assessments_submitted=("id_assessment", "count"),
                                    avg_score=("score", "mean"),
                                    min_score=("score", "min")).reset_index()

    reg = registration[REG_KEYS + ["date_unregistration"]]
    df = (df.merge(vle_f, on=REG_KEYS, how="left")
            .merge(sa_f, on=REG_KEYS, how="left")
            .merge(reg, on=REG_KEYS, how="left"))
    for c in ["total_clicks", "active_days", "clicks_last_2w", "assessments_submitted"]:
        df[c] = df[c].fillna(0).astype(int)
    df["avg_score"] = df["avg_score"].fillna(0.0)
    df["min_score"] = df["min_score"].fillna(0.0)
    df["edu_level"] = df["highest_education"].map(_EDU).fillna(-1)
    df["age_level"] = df["age_band"].map(_AGE).fillna(-1)
    imd = df["imd_band"].astype("string").str.replace(r"^10-20$", "10-20%", regex=True)
    df["imd_level"] = imd.map(_IMD).astype("float").fillna(-1)
    for m in MODULES:
        df[f"module_{m}"] = (df["code_module"] == m).astype(int)
    df["presentation_J"] = df["code_presentation"].str.endswith("J").astype(int)
    df["enrolled_at_k"] = ~(df["date_unregistration"] <= cutoff)
    df["is_withdrawn"] = (df["final_result"] == "Withdrawn").astype(int)
    return df.reset_index(drop=True)


def _rf() -> RandomForestClassifier:
    return RandomForestClassifier(n_estimators=100, max_depth=8, min_samples_leaf=10, max_features="sqrt",
                                  random_state=SEED, n_jobs=-1)


def _positive_class_shap(model: RandomForestClassifier, X: np.ndarray) -> np.ndarray:
    import shap

    raw = shap.TreeExplainer(model).shap_values(X)
    if isinstance(raw, list):
        return np.asarray(raw[1])
    raw = np.asarray(raw)
    return raw[:, :, 1] if raw.ndim == 3 else raw


def fit_out_of_fold(df: pd.DataFrame, calibrate: str | None = None) -> dict:
    """Out-of-fold risk for the registrations still enrolled at week k.

    For each of N_SPLITS GroupKFold folds (groups = id_student) a random forest is
    fitted on the other folds and predicts the held-out fold (`risk_raw`).
    With `calibrate` ("sigmoid" = Platt or "isotonic") the forest is wrapped in
    CalibratedClassifierCV whose calibrators are fitted on separate group folds of
    the training part, and `risk_score` is the calibrated value. The app uses no
    calibration: the pooled forest is already well calibrated
    (audit/academic/risk_model_eval.py).

    Returns {"df": scored rows, "models": forest per fold}; df["fold"] says which
    model held the row out, so `explain` can attribute it.
    """
    d = df.loc[df["enrolled_at_k"]].reset_index(drop=True)
    X = d[FEATURES].to_numpy(dtype=float)
    y = d["is_withdrawn"].to_numpy()
    groups = d["id_student"].to_numpy()
    risk_raw = np.zeros(len(d))
    risk_cal = np.zeros(len(d))
    fold = np.zeros(len(d), dtype=int)
    models = []
    n_splits = min(N_SPLITS, len(np.unique(groups)))
    for i, (tr, te) in enumerate(GroupKFold(n_splits=n_splits).split(X, y, groups)):
        rf = _rf().fit(X[tr], y[tr])
        models.append(rf)
        fold[te] = i
        risk_raw[te] = rf.predict_proba(X[te])[:, 1]
        if calibrate:
            inner = list(GroupKFold(n_splits=3).split(X[tr], y[tr], groups[tr]))
            cal = CalibratedClassifierCV(_rf(), method=calibrate, cv=inner).fit(X[tr], y[tr])
            risk_cal[te] = cal.predict_proba(X[te])[:, 1]
    d["fold"] = fold
    d["risk_raw"] = risk_raw
    d["risk_score"] = risk_cal if calibrate else risk_raw
    d["risk_score_pct"] = (d["risk_score"] * 100).round(1)
    d["risk_level"] = ""
    for _, idx in d.groupby("code_module").groups.items():
        d.loc[idx, "risk_level"] = risk_groups(d.loc[idx, "risk_score"].to_numpy())
    return {"df": d, "models": models}


def explain(d: pd.DataFrame, models: list) -> tuple[pd.DataFrame, np.ndarray]:
    """Signed SHAP (class "withdrawn") of each row's out-of-fold forest + main reason."""
    d = d.reset_index(drop=True).copy()
    shap_vals = np.zeros((len(d), len(FEATURES)))
    for i, model in enumerate(models):
        rows = np.flatnonzero(d["fold"].to_numpy() == i)
        if len(rows):
            shap_vals[rows] = _positive_class_shap(model, d.loc[rows, FEATURES].to_numpy(dtype=float))
    d["top_risk_reason"] = top_reasons(shap_vals, d)
    return d, shap_vals


def risk_groups(score: np.ndarray) -> np.ndarray:
    """HIGH = top 10% by risk, MEDIUM = next 20%, LOW = the rest (rank-based)."""
    n = len(score)
    order = np.argsort(-score, kind="stable")
    rank = np.empty(n, dtype=int)
    rank[order] = np.arange(n)
    n_top = int(np.ceil(TOP_SHARE * n))
    n_mid = int(np.ceil((TOP_SHARE + MID_SHARE) * n))
    return np.where(rank < n_top, "HIGH", np.where(rank < n_mid, "MEDIUM", "LOW"))


def reason_text(feature: str, row: pd.Series) -> str:
    """Human-readable main reason with the student's own value."""
    if feature in ("avg_score", "min_score", "assessments_submitted") and row["assessments_submitted"] == 0:
        return "Нет сданных заданий"
    raw = {"edu_level": "highest_education", "imd_level": "imd_band", "age_level": "age_band"}
    if feature in raw:
        v = row[raw[feature]]
        return f"{FEATURE_LABELS[feature]}: {v}" if pd.notna(v) else FEATURE_LABELS[feature]
    return f"{FEATURE_LABELS[feature]}: {row[feature]:.0f}"


def top_reasons(shap_vals: np.ndarray, d: pd.DataFrame) -> list[str]:
    """Student feature that raises the risk the most (largest positive signed SHAP)."""
    sv = shap_vals[:, :len(STUDENT_FEATURES)]
    out = []
    for i in range(len(sv)):
        j = int(np.argmax(sv[i]))
        out.append(reason_text(STUDENT_FEATURES[j], d.iloc[i]) if sv[i, j] > 0 else NO_RISK_FACTOR)
    return out


def quality(y: np.ndarray, p: np.ndarray) -> dict:
    """AUC, Brier, precision and recall ("охват") among the top 10% by risk."""
    n_top = int(np.ceil(TOP_SHARE * len(p)))
    top = np.argsort(-p, kind="stable")[:n_top]
    pos = int(y.sum())
    return {
        "n": int(len(y)), "positives": pos,
        "auc": float(roc_auc_score(y, p)) if 0 < pos < len(y) else float("nan"),
        "brier": float(brier_score_loss(y, p)),
        "precision_top10": float(y[top].mean()) if n_top else float("nan"),
        "recall_top10": float(y[top].sum() / pos) if pos else float("nan"),
        "base_rate": float(y.mean()),
    }


def reliability(y: np.ndarray, p: np.ndarray, n_bins: int = 10) -> pd.DataFrame:
    """Mean predicted vs observed rate by equal-size bins of predicted risk."""
    bins = pd.qcut(pd.Series(p).rank(method="first"), n_bins, labels=False)
    return (pd.DataFrame({"bin": bins, "pred": p, "obs": y})
              .groupby("bin").agg(pred=("pred", "mean"), obs=("obs", "mean"), n=("obs", "size"))
              .reset_index(drop=True))
