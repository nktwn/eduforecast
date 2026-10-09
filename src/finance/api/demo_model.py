import json
from datetime import datetime, timezone

import lightgbm as lgb
import numpy as np
import pandas as pd

from src.finance.api.features import FEATURES, build_frame, target_frame
from src.finance.config import FINANCE_DATA_DIR, PANEL_PATH
from src.finance.criterion import TARGETS

MODEL_DIR = FINANCE_DATA_DIR / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)
META_PATH = MODEL_DIR / "demo_meta.json"

DEMO_VERSION = "demo-lgbm-0.1"
FIT_MAX_TARGET_YEAR = 2017
CALIBRATION_TARGET_YEAR = 2018
INTERVAL_LEVEL = 0.8
PARAMS = {
    "objective": "regression_l1",
    "n_estimators": 300,
    "learning_rate": 0.05,
    "num_leaves": 15,
    "min_child_samples": 40,
    "subsample": 0.8,
    "subsample_freq": 1,
    "colsample_bytree": 0.8,
    "reg_lambda": 1.0,
    "random_state": 42,
    "verbose": -1,
}


def model_path(target: str):
    return MODEL_DIR / f"{DEMO_VERSION}_{target}.txt"


def train():
    frame = build_frame(pd.read_parquet(PANEL_PATH))
    meta = {"version": DEMO_VERSION, "is_demo": True, "evaluated_against_criterion": False,
            "fit_target_years": f"<= {FIT_MAX_TARGET_YEAR}", "calibration_target_year": CALIBRATION_TARGET_YEAR,
            "trained_through_year": CALIBRATION_TARGET_YEAR, "interval_level": INTERVAL_LEVEL,
            "interval_method": "split conformal, |residual| quantile on calibration year", "features": FEATURES,
            "params": PARAMS, "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "targets": {}}
    for target in TARGETS:
        f = target_frame(frame, target).dropna(subset=["y_next_change", "target_level"])
        fit = f[f["target_year"] <= FIT_MAX_TARGET_YEAR]
        cal = f[f["target_year"] == CALIBRATION_TARGET_YEAR]
        model = lgb.LGBMRegressor(**PARAMS).fit(fit[FEATURES], fit["y_next_change"])
        model.booster_.save_model(str(model_path(target)))
        resid = np.abs(model.predict(cal[FEATURES]) - cal["y_next_change"].to_numpy())
        q = float(np.quantile(resid, min(1.0, np.ceil((len(resid) + 1) * INTERVAL_LEVEL) / len(resid)),
                              method="higher"))
        meta["targets"][target] = {"fit_rows": len(fit), "calibration_rows": len(cal), "interval_half_width": q}
        print(target, meta["targets"][target], flush=True)
    META_PATH.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")


def load():
    meta = json.loads(META_PATH.read_text(encoding="utf-8"))
    boosters = {t: lgb.Booster(model_file=str(model_path(t))) for t in meta["targets"]}
    return meta, boosters


if __name__ == "__main__":
    train()
