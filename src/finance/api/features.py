import numpy as np
import pandas as pd

from src.finance.criterion import GROUP_CHANGE_CLIP, TARGETS

COMMON_FEATURES = {
    "control_public": "Государственный вуз",
    "carnegie_code": "Группа Carnegie",
    "log_fte": "Размер (log FTE)",
    "log_core_real": "Core-расходы на FTE (log)",
    "instruction_share": "Доля расходов на преподавание",
    "institutional_support_share": "Доля институциональной поддержки",
    "student_services_share": "Доля студенческих сервисов",
    "research_share": "Доля исследований",
    "sch_gross_share": "Доля валовых стипендий",
    "fte_per_faculty": "FTE на штатного преподавателя",
    "retention_level": "Retention (текущий год)",
    "grad_level": "Выпускаемость (текущий год)",
    "enroll_growth": "Рост приёма за год",
    "core_real_growth": "Рост core-расходов за год",
}
TARGET_FEATURES = {
    "target_level": "Уровень показателя",
    "target_change_1": "Изменение за последний год",
    "target_change_2": "Изменение годом ранее",
    "group_change": "Средний рост группы за год",
}
FEATURE_LABELS = {**COMMON_FEATURES, **TARGET_FEATURES}
FEATURES = list(COMMON_FEATURES) + list(TARGET_FEATURES)
CARNEGIE_CODES = {g: i for i, g in enumerate(["R1", "R2", "D/PU", "Master's L", "Master's M", "Master's S",
                                               "Baccalaureate", "Special focus", "Tribal", "Other", "Unclassified"])}


def _log(s: pd.Series) -> pd.Series:
    return np.log(s.where(s > 0))


def _lag_change(df: pd.DataFrame, col: str, kind: str, lag: int = 1) -> pd.Series:
    z = _log(df[col]) if kind == "log" else df[col]
    g = df.groupby("series_id")
    prev_z = g[col].shift(lag)
    prev_z = _log(prev_z) if kind == "log" else prev_z
    prev_year = g["year"].shift(lag)
    consecutive = prev_year == df["year"] - lag
    if lag == 1:
        return (z - prev_z).where(consecutive)
    prev2 = g[col].shift(lag - 1)
    prev2 = _log(prev2) if kind == "log" else prev2
    return (prev2 - prev_z).where(consecutive)


def target_series(panel: pd.DataFrame, target: str) -> pd.Series:
    spec = TARGETS[target]
    value = panel[target]
    if spec["eligibility"]:
        value = value.where(panel[spec["eligibility"]])
    return value


def build_frame(panel: pd.DataFrame) -> pd.DataFrame:
    p = panel[~panel["superseded"]].sort_values(["series_id", "year"]).reset_index(drop=True).copy()
    p["control_public"] = (p["control"] == 1).astype(float)
    p["carnegie_code"] = p["carnegie_group"].map(CARNEGIE_CODES).astype(float)
    p["log_fte"] = _log(p["fte_total"])
    p["log_core_real"] = _log(p["core_total_per_fte_real"])
    p["sch_gross_share"] = p["sch_gross_share_of_total_with_discounts"]
    p["retention_level"] = p["retention_rate"]
    p["grad_level"] = p["grad_rate_150"]
    p["enroll_growth"] = _lag_change(p, "fall_enrollment", "log")
    p["core_real_growth"] = _lag_change(p, "core_total_per_fte_real", "log")
    broken = p["id_transition"] | p["merger_absorption"]
    p.loc[broken, ["enroll_growth", "core_real_growth"]] = np.nan
    return p


def target_frame(frame: pd.DataFrame, target: str) -> pd.DataFrame:
    kind = TARGETS[target]["kind"]
    f = frame.copy()
    f["_t"] = target_series(f, target)
    f["target_level"] = _log(f["_t"]) if kind == "log" else f["_t"]
    f["target_change_1"] = _lag_change(f, "_t", kind, 1)
    f["target_change_2"] = _lag_change(f, "_t", kind, 2)
    broken = f["id_transition"] | f["merger_absorption"]
    f.loc[broken, "target_change_1"] = np.nan

    clip = GROUP_CHANGE_CLIP[kind]
    f["group_change"] = f.groupby(["peer_group", "year"])["target_change_1"].transform(
        lambda s: s.clip(-clip, clip).mean() if s.notna().sum() >= 5 else np.nan)

    nxt = f.groupby("series_id")[["target_level", "year", "id_transition", "merger_absorption"]].shift(-1)
    consecutive = nxt["year"] == f["year"] + 1
    clean = ~(nxt["id_transition"].astype(bool) | nxt["merger_absorption"].astype(bool))
    f["y_next_change"] = (nxt["target_level"] - f["target_level"]).where(consecutive & clean)
    f["target_year"] = f["year"] + 1
    return f
