"""Compare recomputed numbers with the numbers in the paper (3 decimals).

Reads results/academic_audit/*.csv produced by steps 1-3 and writes
results/academic_audit/paper_vs_recomputed.csv (+ .md). Network rows are
"not recomputed" when step2 has not produced all three seeds.
Mean ± std over seeds uses the sample standard deviation (ddof=1).
"""
from __future__ import annotations

import pandas as pd

from common import NET_SEEDS, OUT_DIR

NA = "не пересчитано"

# (section, item, paper value)  — numbers as given in the paper.
PAPER_T1 = {  # all test registrations, k = 5/10/20/39
    "LR": ["0.817", "0.862", "0.906", "0.937"],
    "RF": ["0.837", "0.878", "0.920", "0.947"],
    "lstm_full": ["0.710±0.027", "0.803±0.011", "0.886±0.006", "0.942±0.001"],
    "lstm_trunc": ["0.793±0.012", "0.871±0.004", "0.914±0.003", "0.941±0.002"],
    "tft": ["0.797±0.004", "0.870±0.002", "0.915±0.001", "0.942±0.001"],
}
PAPER_T2 = {  # still enrolled, k = 5/10/20
    "LR": ["0.656", "0.680", "0.713"],
    "RF": ["0.692", "0.707", "0.739"],
    "lstm_full": ["0.508±0.029", "0.554±0.016", "0.630±0.018"],
    "lstm_trunc": ["0.622±0.027", "0.696±0.013", "0.738±0.010"],
    "tft": ["0.634±0.005", "0.697±0.004", "0.742±0.003"],
}
NAMES = {"LR": "LR", "RF": "RF", "lstm_full": "LSTM (полные последовательности)",
         "lstm_trunc": "LSTM (случайная обрезка)", "tft": "TFT-inspired"}


def f3(x: float) -> str:
    return f"{x:.3f}"


def main() -> None:
    static = pd.read_csv(OUT_DIR / "static_auc.csv")
    ckpt = pd.read_csv(OUT_DIR / "nets_checkpoints_auc.csv")
    pops = pd.read_csv(OUT_DIR / "populations.csv")
    nets = {}
    for kind in ("lstm_full", "lstm_trunc", "tft"):
        p = OUT_DIR / f"nets_auc_{kind}.csv"
        if p.exists():
            d = pd.read_csv(p)
            if set(d["seed"]) >= set(NET_SEEDS):
                nets[kind] = d[d["seed"].isin(NET_SEEDS)]
    boot_p = OUT_DIR / "bootstrap.csv"
    boot = pd.read_csv(boot_p) if boot_p.exists() else None

    def static_auc(m, k, pop):
        r = static[(static["model"] == m) & (static["k"].astype(str) == str(k)) & (static["population"] == pop)]
        return f3(r["auc"].iloc[0])

    def net_auc(kind, k, pop):
        if kind not in nets:
            return NA
        d = nets[kind]
        a = d[(d["k"].astype(str) == str(k)) & (d["population"] == pop)]["auc"]
        return f"{a.mean():.3f}±{a.std(ddof=1):.3f}"

    def ck(model, method, k, pop="all"):
        r = ckpt[(ckpt["model"] == model) & (ckpt["method"] == method)
                 & (ckpt["k"].astype(str) == str(k)) & (ckpt["population"] == pop)]
        return f3(r["auc"].iloc[0])

    rows = []
    for kind, vals in PAPER_T1.items():
        for k, v in zip([5, 10, 20, 39], vals):
            got = static_auc(kind, k, "all") if kind in ("LR", "RF") else net_auc(kind, k, "all")
            rows.append(("Таблица 1", f"{NAMES[kind]}, k={k}", v, got))
    for kind, vals in PAPER_T2.items():
        for k, v in zip([5, 10, 20], vals):
            got = static_auc(kind, k, "still_enrolled") if kind in ("LR", "RF") else net_auc(kind, k, "still_enrolled")
            rows.append(("Таблица 2", f"{NAMES[kind]}, k={k}", v, got))

    step_k = "weeks<=k, step k"
    t3 = [
        ("RF, весь курс → обрезка k=5 (все)", "0.947 → 0.837",
         f"{static_auc('RF', 'full', 'all')} → {static_auc('RF', 5, 'all')}"),
        ("LSTM опубл. чекпойнт k=5: нули/шаг 39 → шаг k", "0.429 → 0.645",
         f"{ck('LSTM published', 'notebook: weeks<k zero-pad, step 39', 5)} → {ck('LSTM published', step_k, 5)}"),
        ("RF k=5: все → ещё учащиеся", "0.837 → 0.692",
         f"{static_auc('RF', 5, 'all')} → {static_auc('RF', 5, 'still_enrolled')}"),
        ("TFT k=5: все → ещё учащиеся", "0.797 → 0.634",
         f"{net_auc('tft', 5, 'all').split('±')[0]} → {net_auc('tft', 5, 'still_enrolled').split('±')[0]}"
         if "tft" in nets else NA),
        ("LSTM полная последовательность: опубликовано (0.9436) → переобучение (обрезка)", "0.944 → 0.941±0.002",
         f"0.944 (из ноутбука; чекпойнт даёт {ck('LSTM published', step_k, 'full')}) → "
         + (net_auc('lstm_trunc', 39, 'all') if "lstm_trunc" in nets else NA)),
    ]
    rows += [("Таблица 3", a, b, c) for a, b, c in t3]

    if boot is not None:
        def b(k, pop, base="RF"):
            return boot[(boot["k"] == k) & (boot["population"] == pop) & (boot["baseline"] == base)].iloc[0]
        r = b(5, "all")
        rows.append(("Прочее", "TFT−RF, k=5, все", "−0.036", f"{r['tft_minus_baseline']:+.3f}"))
        rows.append(("Прочее", "95% bootstrap-ДИ TFT−RF, k=5", "[−0.043; −0.029]",
                     f"[{r['ci_low']:+.3f}; {r['ci_high']:+.3f}]"))
        r = b(5, "still_enrolled")
        rows.append(("Прочее", "TFT−RF, k=5, ещё учащиеся", "−0.053", f"{r['tft_minus_baseline']:+.3f}"))
    else:
        rows += [("Прочее", "TFT−RF, k=5, все", "−0.036", NA),
                 ("Прочее", "95% bootstrap-ДИ TFT−RF, k=5", "[−0.043; −0.029]", NA),
                 ("Прочее", "TFT−RF, k=5, ещё учащиеся", "−0.053", NA)]

    P = pops.set_index(pops["k"].astype(str))
    rows += [
        ("Прочее", "доля ушедших до старта (k=0)", "31%", f"{P.loc['0', 'share_of_positives']:.1%}"),
        ("Прочее", "доля ушедших к неделе 5", "54%", f"{P.loc['5', 'share_of_positives']:.1%}"),
        ("Прочее", "ещё учащихся k=5/10/20", "5 432 / 5 205 / 4 867",
         " / ".join(f"{int(P.loc[str(k), 'n']):,}".replace(",", " ") for k in (5, 10, 20))),
        ("Прочее", "тест: регистраций / студентов / отчислений", "6 533 / 5 757 / 2 036",
         f"{int(P.loc['all', 'n']):,} / {int(P.loc['all', 'students']):,} / {int(P.loc['all', 'positives']):,}".replace(",", " ")),
        ("Прочее", "обучение: регистраций", "26 060", f"{int(P.loc['all', 'train_registrations']):,}".replace(",", " ")),
    ]

    def match(paper: str, got: str) -> str:
        if got.startswith(NA):
            return "—"
        norm = lambda s: s.replace("−", "-").replace("+", "").replace(" ", "").replace("%", "")
        g = norm(got)
        if "(" in g:  # LSTM row with comment
            g = g.split("→")[0].split("(")[0] + "→" + g.split("→")[1]
        if norm(paper).replace("%", "") == g:
            return "да"
        if "%" in paper:
            return "да" if f"{float(got.rstrip('%')):.0f}" == paper.rstrip("%") else "нет"
        return "нет"

    out = pd.DataFrame(rows, columns=["раздел", "показатель", "в статье", "пересчитано"])
    out["совпало"] = [match(a, b) for a, b in zip(out["в статье"], out["пересчитано"])]
    out.to_csv(OUT_DIR / "paper_vs_recomputed.csv", index=False)
    md = ["| раздел | показатель | в статье | пересчитано | совпало |", "|---|---|---|---|---|"]
    md += ["| " + " | ".join(map(str, r)) + " |" for r in out.itertuples(index=False)]
    (OUT_DIR / "paper_vs_recomputed.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
