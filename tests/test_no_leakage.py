"""The early-warning risk model must not see anything after week k.

Synthetic OULAD-shaped tables, so the test runs without data/raw.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from components import risk_model as rm  # noqa: E402

PRES = ["2013J", "2014B"]


def synthetic(seed: int = 0):
    rng = np.random.default_rng(seed)
    rows = []
    for sid in range(1, 121):
        for module in rng.choice(["AAA", "BBB"], size=rng.integers(1, 3), replace=False):
            rows.append({
                "code_module": module, "code_presentation": rng.choice(PRES), "id_student": sid,
                "gender": rng.choice(["M", "F"]), "region": "London Region",
                "highest_education": rng.choice(["A Level or Equivalent", "Lower Than A Level"]),
                "imd_band": rng.choice(["0-10%", "10-20", "50-60%", np.nan]),
                "age_band": rng.choice(["0-35", "35-55"]),
                "num_of_prev_attempts": int(rng.integers(0, 2)), "studied_credits": int(rng.choice([60, 120])),
                "disability": "N", "final_result": rng.choice(["Pass", "Fail", "Withdrawn"]),
            })
    info = pd.DataFrame(rows).drop_duplicates(rm.REG_KEYS).reset_index(drop=True)
    keys = info[rm.REG_KEYS]
    vle = keys.loc[keys.index.repeat(30)].reset_index(drop=True)
    vle["id_site"] = 1
    vle["date"] = rng.integers(-10, 260, len(vle))
    vle["sum_click"] = rng.integers(1, 20, len(vle))
    assessments = pd.DataFrame([
        {"code_module": m, "code_presentation": p, "id_assessment": 100 * i + j,
         "assessment_type": "TMA", "date": 20 + 30 * j, "weight": 10}
        for i, (m, p) in enumerate([(m, p) for m in ["AAA", "BBB"] for p in PRES]) for j in range(6)
    ])
    sa = keys.merge(assessments[["code_module", "code_presentation", "id_assessment", "date"]],
                    on=["code_module", "code_presentation"])
    sa = sa.sample(frac=0.7, random_state=seed)
    sa["date_submitted"] = sa["date"] + rng.integers(-5, 15, len(sa))
    sa["is_banked"] = 0
    sa["score"] = rng.integers(20, 100, len(sa)).astype(float)
    sa = sa[["id_assessment", "id_student", "date_submitted", "is_banked", "score"]].reset_index(drop=True)
    reg = keys.copy()
    reg["date_registration"] = -30
    reg["date_unregistration"] = np.where(info["final_result"] == "Withdrawn",
                                          rng.integers(-20, 200, len(reg)), np.nan)
    return info, vle, sa, assessments, reg


def features(tables, k):
    df = rm.build_features(*tables, k)
    return df.set_index(rm.REG_KEYS).sort_index()[rm.FEATURES + ["enrolled_at_k"]]


def tamper_after(tables, k, seed=1):
    """Change every piece of data dated after the end of week k."""
    info, vle, sa, assessments, reg = (t.copy() for t in tables)
    rng = np.random.default_rng(seed)
    cutoff = 7 * k
    late = vle["date"] > cutoff
    vle.loc[late, "sum_click"] = rng.integers(500, 900, late.sum())
    extra = vle.sample(50, random_state=seed).assign(date=cutoff + 3, sum_click=999)
    vle = pd.concat([vle, extra], ignore_index=True)
    late = sa["date_submitted"] > cutoff
    sa.loc[late, "score"] = 0.0
    sa = sa.drop(sa.index[late][::2])
    new = sa.head(40).assign(date_submitted=cutoff + 1, score=1.0)
    sa = pd.concat([sa, new], ignore_index=True)
    later = reg["date_unregistration"] > cutoff
    reg.loc[later, "date_unregistration"] = reg.loc[later, "date_unregistration"] + 30
    stay = reg["date_unregistration"].isna()
    reg.loc[stay[stay].index[:10], "date_unregistration"] = cutoff + 5
    return info, vle, sa, assessments, reg


@pytest.mark.parametrize("k", rm.K_OPTIONS)
def test_data_after_week_k_does_not_change_features(k):
    tables = synthetic()
    pd.testing.assert_frame_equal(features(tables, k), features(tamper_after(tables, k), k))


@pytest.mark.parametrize("k", rm.K_OPTIONS)
def test_data_up_to_week_k_does_change_features(k):
    """Guard against a vacuous test: the same kind of edit at day <= 7k is visible."""
    tables = synthetic()
    info, vle, sa, assessments, reg = (t.copy() for t in tables)
    vle.loc[vle["date"] <= 7 * k, "sum_click"] += 1
    assert not features(tables, k).equals(features((info, vle, sa, assessments, reg), k))


def test_out_of_fold_groups_by_student_and_percentile_groups():
    df = rm.build_features(*synthetic(), 10)
    res = rm.fit_out_of_fold(df)
    d = res["df"]
    assert d["enrolled_at_k"].all()
    assert (d.groupby("id_student")["fold"].nunique() == 1).all()
    for _, g in d.groupby("code_module"):
        assert (g["risk_level"] == "HIGH").sum() == int(np.ceil(0.10 * len(g)))
        assert (g["risk_level"] != "LOW").sum() == int(np.ceil(0.30 * len(g)))
    explained, shap_vals = rm.explain(d, res["models"])
    assert shap_vals.shape == (len(d), len(rm.FEATURES))
    assert explained["top_risk_reason"].str.len().gt(0).all()
