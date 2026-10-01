import pandas as pd
import numpy as np
from pathlib import Path
import streamlit as st
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
import shap

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "raw"

FACULTY_MAP = {
    "AAA": "Факультет компьютерных наук",
    "BBB": "Факультет инженерии",
    "CCC": "Факультет бизнеса и экономики",
    "DDD": "Факультет AI и Data Science",
    "EEE": "Факультет математики",
    "FFF": "Факультет естественных наук",
    "GGG": "Факультет социальных наук",
}

RISK_COLORS    = {"HIGH": "#dc2626", "MEDIUM": "#d97706", "LOW": "#059669"}
RISK_LABELS_RU = {"HIGH": "Высокий", "MEDIUM": "Средний", "LOW": "Низкий"}
RESULT_RU      = {
    "Distinction": "Отличие",
    "Pass":        "Зачёт",
    "Fail":        "Незачёт",
    "Withdrawn":   "Отчислен",
}

@st.cache_data(show_spinner="Загрузка данных OULAD...")
def load_raw_data():
    info = pd.read_csv(DATA_DIR / "studentInfo.csv")
    vle = pd.read_csv(
        DATA_DIR / "studentVle.csv",
        dtype={"id_student": "int32", "sum_click": "int32", "date": "int32"},
    )
    assessments_raw = pd.read_csv(DATA_DIR / "studentAssessment.csv")
    assessments = pd.read_csv(DATA_DIR / "assessments.csv")
    registration = pd.read_csv(DATA_DIR / "studentRegistration.csv")
    return info, vle, assessments_raw, assessments, registration

@st.cache_data(show_spinner=False)
def get_faculty_data(module_code: str) -> pd.DataFrame:
    info, vle, assessments_raw, assessments, registration = load_raw_data()

    df = info[info["code_module"] == module_code].copy()

    vle_m = vle[vle["code_module"] == module_code]
    vle_feats = (
        vle_m.groupby("id_student")
        .agg(total_clicks=("sum_click", "sum"), active_days=("date", "nunique"))
        .reset_index()
    )

    module_assess_ids = assessments.loc[
        assessments["code_module"] == module_code, "id_assessment"
    ].tolist()
    sa = assessments_raw[assessments_raw["id_assessment"].isin(module_assess_ids)]
    assess_feats = (
        sa.groupby("id_student")
        .agg(
            assessments_submitted=("id_assessment", "count"),
            avg_score=("score", "mean"),
            min_score=("score", "min"),
        )
        .reset_index()
    )

    reg_m = registration[registration["code_module"] == module_code].copy()
    reg_m["unregistered"] = reg_m["date_unregistration"].notna().astype(int)
    reg_feats = (
        reg_m.groupby("id_student")
        .agg(unregistered=("unregistered", "max"))
        .reset_index()
    )

    df = df.merge(vle_feats, on="id_student", how="left")
    df = df.merge(assess_feats, on="id_student", how="left")
    df = df.merge(reg_feats, on="id_student", how="left")

    for col in ["total_clicks", "active_days", "assessments_submitted", "unregistered"]:
        df[col] = df[col].fillna(0).astype(int)
    df["avg_score"] = df["avg_score"].fillna(0)
    df["min_score"] = df["min_score"].fillna(0)

    return df

@st.cache_data(show_spinner=False)
def get_weekly_activity(module_code: str) -> pd.DataFrame:
    _, vle, _, _, _ = load_raw_data()
    vle_m = vle[(vle["code_module"] == module_code) & (vle["date"] >= 0)].copy()
    vle_m["week"] = (vle_m["date"] // 7).astype(int)
    weekly = (
        vle_m[vle_m["week"] <= 40]
        .groupby("week")
        .agg(total_clicks=("sum_click", "sum"), active_students=("id_student", "nunique"))
        .reset_index()
    )
    return weekly

@st.cache_data(show_spinner=False)
def get_all_faculties_summary() -> pd.DataFrame:
    info, vle, assessments_raw, assessments, _ = load_raw_data()
    rows = []
    for code, name in FACULTY_MAP.items():
        df = info[info["code_module"] == code]
        total = len(df)
        if total == 0:
            continue
        withdrawn = (df["final_result"] == "Withdrawn").sum()

        vle_m = vle[vle["code_module"] == code]
        vle_feats = vle_m.groupby("id_student")["sum_click"].sum().reset_index()
        vle_feats.columns = ["id_student", "total_clicks"]
        merged = df.merge(vle_feats, on="id_student", how="left")
        merged["total_clicks"] = merged["total_clicks"].fillna(0)

        module_assess_ids = assessments.loc[
            assessments["code_module"] == code, "id_assessment"
        ].tolist()
        sa = assessments_raw[assessments_raw["id_assessment"].isin(module_assess_ids)]
        avg_score = sa["score"].mean() if len(sa) > 0 else 0

        active_rate = (merged["total_clicks"] > 10).sum() / total
        withdrawal_rate = withdrawn / total
        health = (1 - withdrawal_rate) * 40 + (avg_score / 100) * 35 + active_rate * 25

        rows.append(
            {
                "module": code,
                "faculty": name,
                "total_students": total,
                "withdrawn": int(withdrawn),
                "withdrawal_rate": round(withdrawal_rate * 100, 1),
                "avg_score": round(avg_score, 1),
                "active_rate": round(active_rate * 100, 1),
                "health_index": round(min(100, max(0, health)), 1),
            }
        )
    return pd.DataFrame(rows)

@st.cache_data(show_spinner="Обучение модели прогнозирования...")
def train_risk_model(module_code: str):
    df = get_faculty_data(module_code).copy()
    df["is_withdrawn"] = (df["final_result"] == "Withdrawn").astype(int)

    le_edu = LabelEncoder()
    le_imd = LabelEncoder()
    le_age = LabelEncoder()
    df["edu_enc"] = le_edu.fit_transform(df["highest_education"].fillna("Unknown"))
    df["imd_enc"] = le_imd.fit_transform(df["imd_band"].fillna("Unknown"))
    df["age_enc"] = le_age.fit_transform(df["age_band"].fillna("Unknown"))

    feature_cols = [
        "total_clicks", "active_days", "assessments_submitted",
        "avg_score", "min_score", "num_of_prev_attempts",
        "studied_credits", "unregistered", "edu_enc", "imd_enc", "age_enc",
    ]
    X_df = df[feature_cols].fillna(0)
    y = df["is_withdrawn"].values

    rf = RandomForestClassifier(
        n_estimators=100, random_state=42, n_jobs=-1, max_depth=8
    )
    rf.fit(X_df.values, y)

    risk_proba = rf.predict_proba(X_df.values)[:, 1]
    df["risk_score"] = risk_proba
    df["risk_score_pct"] = (risk_proba * 100).round(1)
    df["risk_level"] = pd.cut(
        risk_proba,
        bins=[-0.001, 0.3, 0.6, 1.001],
        labels=["LOW", "MEDIUM", "HIGH"],
    ).astype(str)

    explainer = shap.TreeExplainer(rf)
    raw_shap = explainer.shap_values(X_df)

    if isinstance(raw_shap, list):
        shap_vals = np.array(raw_shap[1])
    elif isinstance(raw_shap, np.ndarray) and raw_shap.ndim == 3:
        shap_vals = raw_shap[:, :, 1]
    else:
        shap_vals = np.array(raw_shap)
        if shap_vals.ndim == 3:
            shap_vals = shap_vals[:, :, 1]

    feature_labels = {
        "total_clicks": "Низкая активность в LMS",
        "active_days": "Мало активных дней",
        "assessments_submitted": "Мало сданных заданий",
        "avg_score": "Низкий средний балл",
        "min_score": "Очень низкий минимальный балл",
        "num_of_prev_attempts": "Повторные попытки прохождения",
        "studied_credits": "Сниженная учебная нагрузка",
        "unregistered": "Отменена регистрация",
        "edu_enc": "Уровень начального образования",
        "imd_enc": "Социально-экономический фактор",
        "age_enc": "Возрастная группа",
    }

    def top_reason(row_idx):
        idx = int(np.argmax(np.abs(shap_vals[row_idx])))
        return feature_labels.get(feature_cols[idx], feature_cols[idx])

    df["top_risk_reason"] = [top_reason(i) for i in range(len(df))]
    df.reset_index(drop=True, inplace=True)

    return df, rf, feature_cols, shap_vals

def compute_health_index(df: pd.DataFrame) -> float:
    total = len(df)
    if total == 0:
        return 50.0
    withdrawal_rate = (df["final_result"] == "Withdrawn").sum() / total
    avg_score_norm = df["avg_score"].mean() / 100
    active_rate = (df["total_clicks"] > 10).sum() / total
    health = (1 - withdrawal_rate) * 40 + avg_score_norm * 35 + active_rate * 25
    return round(min(100, max(0, health)), 1)

def get_alerts(df: pd.DataFrame) -> list:
    alerts = []
    total = len(df)
    if total == 0:
        return alerts

    withdrawal_pct = (df["final_result"] == "Withdrawn").sum() / total * 100
    avg_score = df["avg_score"].mean()
    inactive_pct = (df["total_clicks"] == 0).sum() / total * 100

    if withdrawal_pct > 30:
        alerts.append({"level": "КРИТИЧНО", "color": "#dc2626",
                        "msg": f"{withdrawal_pct:.1f}% студентов отчислились — срочное вмешательство необходимо"})
    elif withdrawal_pct > 20:
        alerts.append({"level": "ВНИМАНИЕ", "color": "#d97706",
                        "msg": f"{withdrawal_pct:.1f}% студентов в зоне отчисления — требуется мониторинг"})

    if avg_score < 40:
        alerts.append({"level": "КРИТИЧНО", "color": "#dc2626",
                        "msg": f"Средний балл крайне низкий: {avg_score:.1f}/100"})
    elif avg_score < 55:
        alerts.append({"level": "ВНИМАНИЕ", "color": "#d97706",
                        "msg": f"Средний балл ниже нормы: {avg_score:.1f}/100"})

    if inactive_pct > 15:
        alerts.append({"level": "ПРЕДУПРЕЖДЕНИЕ", "color": "#d97706",
                        "msg": f"{inactive_pct:.1f}% студентов ни разу не открывали материалы курса"})

    if not alerts:
        alerts.append({"level": "НОРМА", "color": "#059669",
                        "msg": "Все ключевые показатели в пределах нормы"})
    return alerts

def get_retention_data(module_code: str):
    _, _, _, _, registration = load_raw_data()
    reg = registration[registration["code_module"] == module_code].copy()

    total = reg["id_student"].nunique()
    reg["date_unregistration"] = pd.to_numeric(
        reg["date_unregistration"], errors="coerce"
    )
    unreg = reg.dropna(subset=["date_unregistration"]).copy()
    unreg["week"] = (unreg["date_unregistration"] // 7).clip(lower=0).astype(int)

    weekly_drop = unreg[unreg["week"] >= 0].groupby("week")["id_student"].count()

    max_week = 38
    survived = [total]
    for w in range(1, max_week + 1):
        survived.append(max(0, survived[-1] - weekly_drop.get(w, 0)))

    survived_pct = [s / total * 100 for s in survived]
    weeks_hist = list(range(max_week + 1))

    window = 8
    if len(survived_pct) >= window:
        slope = (survived_pct[-1] - survived_pct[-window]) / window
    else:
        slope = -0.2
    forecast_weeks = list(range(max_week + 1, max_week + 13))
    forecast_pct = [max(0, survived_pct[-1] + slope * i) for i in range(1, 13)]

    return weeks_hist, survived_pct, forecast_weeks, forecast_pct
