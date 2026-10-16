"""Students page risk model: before vs after (stage B), calibration check.

Before: the former app model (app/components/data_loader.py up to commit 5d54da3):
full-course features, RF fitted and scored on the same students ("in-sample"),
and the same model scored out-of-fold (GroupKFold by student) for reference.
After: app/components/risk_model.py — features up to week k, pooled RF,
out-of-fold risk for students still enrolled at week k; at k = 5 also Platt and
isotonic calibration fitted on separate folds.

  python risk_model_eval.py      # ~1-2 min

Output: results/academic_audit/risk_model_eval.csv, risk_model_reliability_k5.csv
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import LabelEncoder

from common import OUT_DIR, ROOT, load_raw

sys.path.insert(0, str(ROOT / "app"))
from components import risk_model as rm  # noqa: E402

MODULES = rm.MODULES


def old_model(raw: dict, code: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The former train_risk_model, verbatim features and RF settings."""
    info, vle, sa, ass = raw["studentInfo"], raw["studentVle"], raw["studentAssessment"], raw["assessments"]
    df = info[info["code_module"] == code].copy()
    vm = vle[vle["code_module"] == code]
    vf = vm.groupby("id_student").agg(total_clicks=("sum_click", "sum"), active_days=("date", "nunique")).reset_index()
    s = sa[sa["id_assessment"].isin(ass.loc[ass["code_module"] == code, "id_assessment"])]
    af = s.groupby("id_student").agg(assessments_submitted=("id_assessment", "count"),
                                     avg_score=("score", "mean"), min_score=("score", "min")).reset_index()
    df = df.merge(vf, on="id_student", how="left").merge(af, on="id_student", how="left")
    for c in ["total_clicks", "active_days", "assessments_submitted", "avg_score", "min_score"]:
        df[c] = df[c].fillna(0)
    for c, n in [("highest_education", "edu_enc"), ("imd_band", "imd_enc"), ("age_band", "age_enc")]:
        df[n] = LabelEncoder().fit_transform(df[c].fillna("Unknown"))
    fc = ["total_clicks", "active_days", "assessments_submitted", "avg_score", "min_score",
          "num_of_prev_attempts", "studied_credits", "edu_enc", "imd_enc", "age_enc"]
    X, y = df[fc].fillna(0).to_numpy(), (df["final_result"] == "Withdrawn").astype(int).to_numpy()

    def rf():
        return RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1, max_depth=8)

    in_sample = rf().fit(X, y).predict_proba(X)[:, 1]
    oof = np.zeros(len(y))
    for tr, te in GroupKFold(5).split(X, y, df["id_student"]):
        oof[te] = rf().fit(X[tr], y[tr]).predict_proba(X[te])[:, 1]
    return y, in_sample, oof


def main() -> None:
    raw = load_raw()
    tables = (raw["studentInfo"], raw["studentVle"], raw["studentAssessment"],
              raw["assessments"], raw["studentRegistration"])
    rows = []

    def add(variant, module, y, p):
        rows.append({"variant": variant, "module": module, **rm.quality(y, p)})

    ys, ins, oofs = [], [], []
    for code in MODULES:
        y, a, b = old_model(raw, code)
        add("before: in-sample, all students, full course", code, y, a)
        add("before: same model out-of-fold, full course", code, y, b)
        ys.append(y), ins.append(a), oofs.append(b)
    add("before: in-sample, all students, full course", "ALL", np.concatenate(ys), np.concatenate(ins))
    add("before: same model out-of-fold, full course", "ALL", np.concatenate(ys), np.concatenate(oofs))

    for k in rm.K_OPTIONS:
        feats = rm.build_features(*tables, k)
        for cal in ([None, "sigmoid", "isotonic"] if k == 5 else [None]):
            d = rm.fit_out_of_fold(feats, calibrate=cal)["df"]
            name = f"after: k={k}, still enrolled, out-of-fold" + (f", {cal}" if cal else "")
            for code in MODULES:
                g = d[d["code_module"] == code]
                add(name, code, g["is_withdrawn"].to_numpy(), g["risk_score"].to_numpy())
            add(name, "ALL", d["is_withdrawn"].to_numpy(), d["risk_score"].to_numpy())
            if k == 5:
                rel = rm.reliability(d["is_withdrawn"].to_numpy(), d["risk_score"].to_numpy())
                rel.insert(0, "calibration", cal or "none")
                rows_rel = rel if cal is None else pd.concat([rows_rel, rel])
        print(f"k={k} done", flush=True)

    out = pd.DataFrame(rows)
    num = out.select_dtypes("float").columns
    out[num] = out[num].round(6)
    out.to_csv(OUT_DIR / "risk_model_eval.csv", index=False)
    rows_rel.round(6).to_csv(OUT_DIR / "risk_model_reliability_k5.csv", index=False)
    pd.set_option("display.width", 200)
    print(out[out["module"] == "ALL"].drop(columns="module").round(3).to_string(index=False))


if __name__ == "__main__":
    main()
