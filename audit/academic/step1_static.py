"""Step 1: static features truncated to weeks <= k; LR and RF (ACADEMIC_AUDIT.md §1.2, §3).

Outputs (results/academic_audit/):
  populations.csv          test-set sizes, withdrawals by week k, still-enrolled counts
  static_auc.csv           LR/RF AUC per k, all test registrations and still-enrolled only
  predictions/static_k{k}.csv   per-registration probabilities (gitignored)
"""
from __future__ import annotations

import time

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler

from common import (KS, OUT_DIR, PRED_DIR, PROCESSED_DIR, REG_KEYS, SEED, TARGET,
                    build_static, ensure_dirs, feature_cols, load_raw, split_ids,
                    still_enrolled, unregistration)


def check_full_rebuild(raw, feats) -> float:
    """Rebuilding without truncation must reproduce data/processed exactly."""
    full = build_static(raw, None)
    train_ids, test_ids = split_ids()
    worst = 0.0
    for name, ids in (("train", train_ids), ("test", test_ids)):
        mine = full[full["id_student"].isin(ids)].reset_index(drop=True)
        ref = pd.read_csv(PROCESSED_DIR / f"{name}_static.csv")
        assert (mine[REG_KEYS].to_numpy() == ref[REG_KEYS].to_numpy()).all(), f"{name}: row order differs"
        worst = max(worst, float(np.abs(mine[feats].to_numpy(float) - ref[feats].to_numpy(float)).max()))
    return worst


def fit_predict(train: pd.DataFrame, test: pd.DataFrame, feats: list[str]) -> dict[str, np.ndarray]:
    """Preprocessing and hyperparameters of notebooks/03_baseline."""
    scaler = StandardScaler()
    Xtr = scaler.fit_transform(train[feats].to_numpy())
    Xte = scaler.transform(test[feats].to_numpy())
    ytr = train[TARGET].to_numpy()
    lr = LogisticRegression(max_iter=1000, random_state=SEED, class_weight="balanced").fit(Xtr, ytr)
    rf = RandomForestClassifier(n_estimators=200, max_depth=10, random_state=SEED,
                                class_weight="balanced", n_jobs=-1).fit(Xtr, ytr)
    return {"LR": lr.predict_proba(Xte)[:, 1], "RF": rf.predict_proba(Xte)[:, 1]}


def main() -> None:
    ensure_dirs()
    t0 = time.time()
    raw = load_raw()
    feats = feature_cols()
    train_ids, test_ids = split_ids()
    unreg = unregistration(raw)

    diff = check_full_rebuild(raw, feats)
    print(f"full-course rebuild vs data/processed: max |diff| = {diff}")
    assert diff == 0.0

    # Populations
    test_keys = pd.read_csv(PROCESSED_DIR / "test_static.csv", usecols=REG_KEYS + [TARGET])
    n_train = len(pd.read_csv(PROCESSED_DIR / "train_static.csv", usecols=["id_student"]))
    y = test_keys[TARGET].to_numpy()
    rows = [{"k": "all", "n": len(test_keys), "students": test_keys["id_student"].nunique(),
             "positives": int(y.sum()), "train_registrations": n_train}]
    for k in [0] + KS:
        enr = still_enrolled(test_keys, unreg, k)
        rows.append({"k": k, "withdrawn_by_k": int((~enr).sum()),
                     "withdrawn_by_k_positive": int((~enr & (y == 1)).sum()),
                     "share_of_positives": round(float((~enr & (y == 1)).sum() / y.sum()), 6),
                     "n": int(enr.sum()), "positives": int(y[enr].sum())})
    pd.DataFrame(rows).to_csv(OUT_DIR / "populations.csv", index=False)
    print(pd.DataFrame(rows).to_string(index=False))

    # Full-course baseline (as published) + truncated LR/RF
    res = []
    full = build_static(raw, None)
    for k in [None] + KS:
        static = full if k is None else build_static(raw, k)
        train = static[static["id_student"].isin(train_ids)].reset_index(drop=True)
        test = static[static["id_student"].isin(test_ids)].reset_index(drop=True)
        probs = fit_predict(train, test, feats)
        label = "full" if k is None else k
        yt = test[TARGET].to_numpy()
        pred = test[REG_KEYS + [TARGET]].copy()
        for m, p in probs.items():
            pred[m] = p.round(6)
            res.append({"model": m, "k": label, "population": "all", "n": len(yt),
                        "positives": int(yt.sum()), "auc": roc_auc_score(yt, p)})
            if k is not None:
                enr = still_enrolled(test, unreg, k)
                res.append({"model": m, "k": label, "population": "still_enrolled",
                            "n": int(enr.sum()), "positives": int(yt[enr].sum()),
                            "auc": roc_auc_score(yt[enr], p[enr])})
        pred.to_csv(PRED_DIR / f"static_k{label}.csv", index=False)
        print(f"k={label}: done ({time.time() - t0:.0f}s)")

    out = pd.DataFrame(res)
    out["auc"] = out["auc"].round(6)
    out.to_csv(OUT_DIR / "static_auc.csv", index=False)
    print(out.to_string(index=False))
    print(f"total {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
