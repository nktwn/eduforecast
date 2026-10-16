"""Provider for the stage-2 model (LightGBM S3), evaluated against the pre-registered criterion.

Same JSON contract as the demo provider. The model is the evaluated procedure refitted on
target years <= 2023 (models_stage2.deploy); the interval is split conformal normalized by the
series' volatility of changes. Targets whose model failed the criterion get CRITERION_NOT_MET.
"""
import json

import lightgbm as lgb
import numpy as np
import pandas as pd

from src.finance import criterion_stage2 as C
from src.finance.api.contract import CONTRACT_VERSION, TARGET_META, flag
from src.finance.api.providers import (DATA_VINTAGE, HORIZON_YEAR, DemoProvider, FinanceRepository, _collect_flags,
                                       _num, _to_level)
from src.finance.config import YEAR_MAX
from src.finance.criterion import TARGETS
from src.finance.models_stage2 import MODEL_DIR, _sigma, common_features, target_frame
from src.finance.panel_stage2 import PANEL2_PATH

META_PATH = MODEL_DIR / "deploy_meta.json"
LABELS = {
    "target_level": "Уровень показателя (текущий год)", "target_change_1": "Изменение за последний год",
    "target_change_2": "Изменение годом ранее", "target_change_3": "Изменение два года назад",
    "log_fte": "Размер (log FTE)", "log_enrollment": "Приём (log)", "control_public": "Государственный вуз",
    "carnegie": "Группа Carnegie", "log_core_real": "Core-расходы на FTE (log)",
    "core_real_growth_1": "Рост core-расходов за год", "core_real_growth_2": "Рост core-расходов годом ранее",
    "nat_compensation_share": "Доля оплаты труда", "nat_depreciation_share": "Доля амортизации",
    "nat_interest_share": "Доля процентов", "sch_gross_share": "Доля валовых стипендий",
    "admit_rate": "Доля принятых", "yield_rate": "Yield", "pell_share_ug": "Доля студентов с Pell",
    "log_net_price_real": "Чистая цена (log)", "log_tuition_instate_real": "Плата за обучение (log)",
    "inst_aid_share_ftft": "Доля с институциональной помощью", "log_faculty_salary_real": "Зарплата преподавателей (log)",
    "ft_instr_staff_share": "Доля штатных преподавателей", "fte_per_faculty": "FTE на штатного преподавателя",
    "full_time_share": "Доля очных студентов", "graduate_share": "Доля магистрантов и аспирантов",
}


def label(feature: str) -> str:
    if feature in LABELS:
        return LABELS[feature]
    if feature.startswith("deg_share_"):
        return "Доля выпускников: " + feature.removeprefix("deg_share_").replace("_", " ")
    base = feature.removesuffix("_lag1").removesuffix("_share_ops").replace("_", " ")
    if feature.startswith("log_") and feature.endswith("_real"):
        return f"Расходы на FTE: {feature[4:-5].replace('_', ' ')} (log)"
    return f"Доля функции «{base}»" + (" год назад" if feature.endswith("_lag1") else "")


class Stage2Provider(DemoProvider):
    name = "stage2-lightgbm"

    def __init__(self, repo: FinanceRepository | None = None):
        self.repo = repo or FinanceRepository()
        self.meta = json.loads(META_PATH.read_text(encoding="utf-8"))
        self.boosters = {t: lgb.Booster(model_file=str(MODEL_DIR / f"deploy_{t}.txt")) for t in TARGETS}
        panel2 = pd.read_parquet(PANEL2_PATH)
        common = common_features(panel2)
        self.frames = {t: target_frame(panel2, common, t) for t in TARGETS}
        self.sigmas = {t: _sigma(self.frames[t], YEAR_MAX) for t in TARGETS}

    def passed(self, target: str) -> bool | None:
        crit = self.meta["targets"][target].get("criterion")
        if not crit:
            return None
        return all(v["meets_success_rule"] for v in crit.values())

    def _target_block(self, series_id: int, target: str, peer_ids: list[int]) -> dict:
        block = self._base_block(series_id, target, peer_ids)
        if not block["eligible"]:
            return block
        meta, scale = self.meta["targets"][target], TARGET_META[target]["change_scale"]
        f = self.frames[target]
        row = f[(f["series_id"] == series_id) & (f["year"] == YEAR_MAX)]
        last_value = block["baselines"][0]["value"]
        if row.empty or pd.isna(row["target_level"].iloc[0]):
            block.update({"eligible": False, "ineligible_reason": f"Нет признаков за {YEAR_MAX} год",
                          "baselines": []})
            return block
        features = self.meta["features"]
        x = row[features].astype(float)
        booster = self.boosters[target]
        change = float(booster.predict(x)[0])
        contrib = booster.predict(x, pred_contrib=True)[0]
        sigma = self.sigmas[target].get(series_id, np.nan)
        sigma = max(meta["sigma_median"] if pd.isna(sigma) else float(sigma), meta["sigma_floor"])
        half = meta["qhat"] * sigma
        block["forecast"] = {
            "year": HORIZON_YEAR, "value": _to_level(last_value, change, scale), "predicted_change": change,
            "interval": {"level": self.meta["interval_level"], "lower": _to_level(last_value, change - half, scale),
                         "upper": _to_level(last_value, change + half, scale),
                         "method": "split conformal, нормированный на волатильность ряда (калибровка: 2023 год)"},
        }
        block["explanation"] = {
            "method": "TreeSHAP (LightGBM pred_contrib)", "scale": scale, "base_value": float(contrib[-1]),
            "prediction": change,
            "contributions": [{"feature": f_, "label": label(f_), "feature_value": _num(x[f_].iloc[0]),
                               "contribution": float(c)} for f_, c in zip(features, contrib[:-1])],
        }
        return block

    def forecast(self, series_id: int) -> dict:
        peers = self.repo.peers(series_id)
        peer_ids = peers["series_id"].astype(int).tolist()
        targets = [self._target_block(series_id, t, peer_ids) for t in TARGETS]
        extra = [flag("CRITERION_NOT_MET", target=t) for t in TARGETS if self.passed(t) is False]
        if len(self.repo.rows(series_id)) < 5:
            extra.append(flag("SHORT_HISTORY"))
        failed = [TARGET_META[t]["label"] for t in TARGETS if self.passed(t) is False]
        return {
            "contract_version": CONTRACT_VERSION, "generated_at": pd.Timestamp.now("UTC").isoformat(timespec="seconds"),
            "provider": {"name": self.name, "is_mock": False, "is_demo": False, "model_version": self.meta["version"],
                         "trained_through_year": self.meta["trained_through_year"],
                         "evaluated_against_criterion": True,
                         "notes": "LightGBM S3, процедура оценена rolling origin 2014–2022 по критерию "
                                  f"{C.SUCCESS_MIN_RELATIVE_MAE_GAIN:.0%}; не прошли критерий: "
                                  f"{', '.join(failed) if failed else 'нет'}."},
            "institution": self.repo.institution(series_id), "data_vintage": DATA_VINTAGE,
            "horizon_year": HORIZON_YEAR, "targets": targets, "peers": self.repo.peer_records(peers),
            "data_quality": {"flags": _collect_flags(targets, extra)},
        }
