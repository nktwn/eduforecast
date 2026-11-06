"""Step 3: student-level bootstrap of AUC differences (ACADEMIC_AUDIT.md §4).

Needs predictions from step1 and step2 (results/academic_audit/predictions/).
TFT-inspired (seed 42) is compared with each baseline: LR and RF (truncated),
LSTM full and LSTM truncated (seed 42). 2000 resamples of students with
replacement; all registrations of a drawn student enter together.

Output: results/academic_audit/bootstrap.csv
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from common import KS, OUT_DIR, PRED_DIR, REG_KEYS, SEED, TARGET, load_raw, still_enrolled, unregistration

N_BOOT = 2000


def main() -> None:
    unreg = unregistration(load_raw())
    nets = {name: pd.read_csv(PRED_DIR / f"{name}_seed42.csv") for name in ("tft", "lstm_full", "lstm_trunc")}
    rows = []
    for k in KS:
        df = pd.read_csv(PRED_DIR / f"static_k{k}.csv")
        for name, p in nets.items():
            df = df.merge(p[REG_KEYS + [f"k{k}"]].rename(columns={f"k{k}": name}), on=REG_KEYS, how="inner")
        assert len(df) == len(nets["tft"])
        enr = still_enrolled(df, unreg, k)
        for pop, mask in (("all", np.ones(len(df), bool)), ("still_enrolled", enr)):
            d = df[mask].reset_index(drop=True)
            y = d[TARGET].to_numpy()
            students, inv = np.unique(d["id_student"].to_numpy(), return_inverse=True)
            rng = np.random.default_rng(SEED)
            draws = [np.bincount(rng.integers(0, len(students), len(students)), minlength=len(students))[inv]
                     for _ in range(N_BOOT)]
            auc_tft = roc_auc_score(y, d["tft"])
            boot_tft = np.array([roc_auc_score(y, d["tft"], sample_weight=w) for w in draws])
            for base, col in (("LR", "LR"), ("RF", "RF"), ("LSTM full", "lstm_full"), ("LSTM trunc", "lstm_trunc")):
                auc_b = roc_auc_score(y, d[col])
                boot_b = np.array([roc_auc_score(y, d[col], sample_weight=w) for w in draws])
                diff = boot_tft - boot_b
                rows.append({"k": k, "population": pop, "n": len(d), "positives": int(y.sum()),
                             "baseline": base, "auc_baseline": round(auc_b, 6), "auc_tft_seed42": round(auc_tft, 6),
                             "tft_minus_baseline": round(auc_tft - auc_b, 6),
                             "ci_low": round(float(np.percentile(diff, 2.5)), 6),
                             "ci_high": round(float(np.percentile(diff, 97.5)), 6)})
            print(f"k={k} {pop}: done", flush=True)
    out = pd.DataFrame(rows)
    out["best_baseline"] = out.groupby(["k", "population"])["auc_baseline"].transform("max") == out["auc_baseline"]
    out.to_csv(OUT_DIR / "bootstrap.csv", index=False)
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
