"""Step 2: sequence models (ACADEMIC_AUDIT.md §2, §4).

  python step2_nets.py checkpoints          # published .pth files, no training (~1 min)
  python step2_nets.py train [--models lstm_full lstm_trunc tft] [--seeds 42 43 44]
  python step2_nets.py rescore              # AUC from saved predictions, no training

Training follows notebooks/04_lstm and 05_tft (2x64 LSTM, Adam 1e-3, batch 64,
pos_weight, grad clip 1.0, 30 epochs, patience 5) with two changes from the audit:
  * the epoch is selected on a validation split of TRAIN students (10%, stratified
    by student), never on the test set;
  * everything runs on CPU (MPS training is unstable in torch 2.12, §2.4).
"lstm_trunc" uses the TFT random-truncation scheme (75% of samples cut to a random
length t in [1, 40]) and reads the hidden state at step t-1.
Evaluation at week k feeds weeks 0..k and reads the output at step k.

Outputs (results/academic_audit/):
  nets_checkpoints_auc.csv, nets_auc_{model}.csv (one row per seed/k/population)
  predictions/{model}_seed{seed}.csv (gitignored)
"""
from __future__ import annotations

import argparse
import copy
import time

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split

from common import (KS, NET_SEEDS, N_WEEKS, OUT_DIR, PRED_DIR, RESULTS_DIR, TARGET,
                    ensure_dirs, load_raw, load_sequences, set_seed, still_enrolled,
                    unregistration)

DEVICE = torch.device("cpu")
EPOCHS, LR, PATIENCE, BATCH, MASK_PROB = 30, 1e-3, 5, 64, 0.75


class StudentLSTM(nn.Module):
    """notebooks/04_lstm. forward(x, lengths) reads the output at step lengths-1."""

    def __init__(self, input_size=7, hidden_size=64, num_layers=2, dropout=0.2):
        super().__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True,
                            dropout=dropout if num_layers > 1 else 0.0)
        self.classifier = nn.Sequential(nn.Linear(hidden_size, 32), nn.ReLU(),
                                        nn.Dropout(dropout), nn.Linear(32, 1))

    def forward(self, x, lengths=None):
        out, _ = self.lstm(x)
        if lengths is None:
            last = out[:, -1, :]
        else:
            last = out[torch.arange(len(x)), lengths - 1]
        return self.classifier(last).squeeze(-1)


class TemporalAttentionModel(nn.Module):
    """notebooks/05_tft (TFT-inspired), unchanged."""

    def __init__(self, input_size=7, hidden_size=64, num_layers=2, num_heads=4, dropout=0.1):
        super().__init__()
        self.input_proj = nn.Sequential(nn.Linear(input_size, hidden_size), nn.ReLU())
        self.lstm = nn.LSTM(hidden_size, hidden_size, num_layers, batch_first=True,
                            dropout=dropout if num_layers > 1 else 0.0)
        self.attention = nn.MultiheadAttention(hidden_size, num_heads, dropout=dropout,
                                               batch_first=True)
        self.layer_norm = nn.LayerNorm(hidden_size)
        self.classifier = nn.Sequential(nn.Linear(hidden_size, hidden_size // 2), nn.ReLU(),
                                        nn.Dropout(dropout), nn.Linear(hidden_size // 2, 1))

    def forward(self, x, key_padding_mask=None):
        h, _ = self.lstm(self.input_proj(x))
        a, _ = self.attention(h, h, h, key_padding_mask=key_padding_mask, need_weights=False)
        z = self.layer_norm(a + h)
        if key_padding_mask is not None:
            valid = (~key_padding_mask).float().unsqueeze(-1)
            pooled = (z * valid).sum(1) / valid.sum(1).clamp(min=1)
        else:
            pooled = z.mean(1)
        return self.classifier(pooled).squeeze(-1)


def logits_prefix(model, X: torch.Tensor, n_steps: int | torch.Tensor) -> torch.Tensor:
    """Model output given weeks 0..n_steps-1 (per-sample lengths allowed)."""
    B, T, _ = X.shape
    lengths = torch.full((B,), n_steps, dtype=torch.long) if isinstance(n_steps, int) else n_steps
    if isinstance(model, StudentLSTM):
        return model(X, lengths)
    pad = torch.arange(T).unsqueeze(0) >= lengths.unsqueeze(1)
    Xm = X.masked_fill(pad.unsqueeze(-1), 0.0)
    return model(Xm, key_padding_mask=pad if (pad.any()) else None)


@torch.no_grad()
def predict(model, X: np.ndarray, n_steps: int, bs: int = 1024) -> np.ndarray:
    model.eval()
    Xt = torch.from_numpy(X)
    return np.concatenate([torch.sigmoid(logits_prefix(model, Xt[i:i + bs], n_steps)).numpy()
                           for i in range(0, len(Xt), bs)])


def train_one(kind: str, seed: int, Xtr, ytr, Xva, yva) -> tuple[nn.Module, dict]:
    t0 = time.time()
    set_seed(seed)
    model = StudentLSTM() if kind.startswith("lstm") else TemporalAttentionModel()
    wd = 1e-4 if kind == "tft" else 0.0
    opt = torch.optim.Adam(model.parameters(), lr=LR, weight_decay=wd)
    pos_weight = torch.tensor([(len(ytr) - ytr.sum()) / ytr.sum()], dtype=torch.float32)
    crit = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    gen = torch.Generator().manual_seed(seed)
    Xt, yt = torch.from_numpy(Xtr), torch.from_numpy(ytr)
    truncate = kind in ("lstm_trunc", "tft")

    best, best_auc, best_epoch, bad = None, -1.0, 0, 0
    for epoch in range(1, EPOCHS + 1):
        model.train()
        perm = torch.randperm(len(Xt), generator=gen)
        for i in range(0, len(perm), BATCH):
            idx = perm[i:i + BATCH]
            xb, yb = Xt[idx], yt[idx]
            if truncate:
                B = len(idx)
                cut = torch.rand(B, generator=gen) < MASK_PROB
                t = torch.randint(1, N_WEEKS + 1, (B,), generator=gen)
                lengths = torch.where(cut, t, torch.full_like(t, N_WEEKS))
                logits = logits_prefix(model, xb, lengths)
            else:
                logits = model(xb)
            loss = crit(logits, yb)
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            opt.step()
        val_auc = roc_auc_score(yva, predict(model, Xva, N_WEEKS))
        print(f"  {kind} seed {seed} epoch {epoch}: val AUC {val_auc:.4f} ({time.time() - t0:.0f}s)", flush=True)
        if val_auc > best_auc:
            best_auc, best_epoch, bad = val_auc, epoch, 0
            best = copy.deepcopy(model.state_dict())
        else:
            bad += 1
        if bad >= PATIENCE:
            break
    model.load_state_dict(best)
    return model, {"best_epoch": best_epoch, "val_auc": best_auc, "epochs_run": epoch}


def evaluate(model, Xte, yte, enrolled: dict[int, np.ndarray], tag: dict) -> tuple[list, dict]:
    rows, preds = [], {}
    for k in KS:
        p = predict(model, Xte, k + 1)
        preds[f"k{k}"] = p
        rows.append({**tag, "k": k, "population": "all", "auc": roc_auc_score(yte, p)})
        m = enrolled[k]
        rows.append({**tag, "k": k, "population": "still_enrolled", "auc": roc_auc_score(yte[m], p[m])})
    p = predict(model, Xte, N_WEEKS)
    preds["full"] = p
    rows.append({**tag, "k": "full", "population": "all", "auc": roc_auc_score(yte, p)})
    return rows, preds


def checkpoints(Xte, yte, enrolled) -> None:
    rows = []
    lstm = StudentLSTM()
    lstm.load_state_dict(torch.load(RESULTS_DIR / "lstm_best_model.pth", map_location="cpu"))
    tft = TemporalAttentionModel()
    tft.load_state_dict(torch.load(RESULTS_DIR / "tft_best_model.pth", map_location="cpu"))
    for name, model in (("LSTM published", lstm), ("TFT published", tft)):
        r, _ = evaluate(model, Xte, yte, enrolled, {"model": name, "method": "weeks<=k, step k"})
        rows += r
    # As in the notebooks: weeks 0..k-1 kept, the rest zeroed after scaling.
    lstm.eval(), tft.eval()
    Xt = torch.from_numpy(Xte)
    for k in KS:
        Xm = Xt.clone()
        Xm[:, k:, :] = 0.0
        with torch.no_grad():
            p_lstm = torch.sigmoid(lstm(Xm)).numpy()  # read at step 39, as in 04_lstm
            pm = torch.zeros(len(Xm), N_WEEKS, dtype=torch.bool)
            pm[:, k:] = True
            p_tft = torch.sigmoid(tft(Xm, key_padding_mask=pm)).numpy()
        rows.append({"model": "LSTM published", "method": "notebook: weeks<k zero-pad, step 39",
                     "k": k, "population": "all", "auc": roc_auc_score(yte, p_lstm)})
        rows.append({"model": "TFT published", "method": "notebook: weeks<k",
                     "k": k, "population": "all", "auc": roc_auc_score(yte, p_tft)})
    out = pd.DataFrame(rows)
    out["auc"] = out["auc"].round(6)
    out.to_csv(OUT_DIR / "nets_checkpoints_auc.csv", index=False)
    print(out.to_string(index=False))


def rescore(models: list[str], seeds: list[int], enrolled: dict[int, np.ndarray]) -> None:
    """Recompute nets_auc_{model}.csv from predictions/{model}_seed{seed}.csv."""
    for kind in models:
        out_csv = OUT_DIR / f"nets_auc_{kind}.csv"
        meta = pd.read_csv(out_csv).drop_duplicates("seed").set_index("seed")
        rows = []
        for seed in seeds:
            p = pd.read_csv(PRED_DIR / f"{kind}_seed{seed}.csv")
            y = p[TARGET].to_numpy()
            tag = {"model": kind, "seed": seed,
                   **meta.loc[seed, ["best_epoch", "val_auc", "epochs_run", "train_seconds"]].to_dict()}
            for k in KS:
                m = enrolled[k]
                rows.append({**tag, "k": k, "population": "all", "auc": roc_auc_score(y, p[f"k{k}"])})
                rows.append({**tag, "k": k, "population": "still_enrolled",
                             "auc": roc_auc_score(y[m], p[f"k{k}"].to_numpy()[m])})
            rows.append({**tag, "k": "full", "population": "all", "auc": roc_auc_score(y, p["full"])})
        out = pd.DataFrame(rows)
        out["auc"] = out["auc"].round(6)
        out.to_csv(out_csv, index=False)
        print(f"{out_csv.name}: {len(out)} rows")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("part", choices=["checkpoints", "train", "rescore"])
    ap.add_argument("--models", nargs="+", default=["lstm_full", "lstm_trunc", "tft"])
    ap.add_argument("--seeds", nargs="+", type=int, default=NET_SEEDS)
    ap.add_argument("--threads", type=int, default=0, help="torch CPU threads (0 = default)")
    args = ap.parse_args()
    ensure_dirs()
    if args.threads:
        torch.set_num_threads(args.threads)

    Xtr, ytr, Xte, yte, ktr, kte = load_sequences()
    unreg = unregistration(load_raw())
    enrolled = {k: still_enrolled(kte, unreg, k) for k in KS}

    if args.part == "checkpoints":
        checkpoints(Xte, yte, enrolled)
        return
    if args.part == "rescore":
        rescore(args.models, args.seeds, enrolled)
        return

    # Validation = 10% of train students, stratified by student-level label.
    stud = ktr.assign(y=ytr).groupby("id_student")["y"].max()
    _, val_ids = train_test_split(stud.index, test_size=0.1, random_state=42, stratify=stud.values)
    is_val = ktr["id_student"].isin(set(val_ids)).to_numpy()

    for kind in args.models:
        out_csv = OUT_DIR / f"nets_auc_{kind}.csv"
        done = pd.read_csv(out_csv) if out_csv.exists() else pd.DataFrame()
        for seed in args.seeds:
            t0 = time.time()
            model, info = train_one(kind, seed, Xtr[~is_val], ytr[~is_val], Xtr[is_val], ytr[is_val])
            tag = {"model": kind, "seed": seed, **info, "train_seconds": round(time.time() - t0)}
            rows, preds = evaluate(model, Xte, yte, enrolled, tag)
            pd.DataFrame({**{c: kte[c] for c in kte.columns}, TARGET: yte,
                          **{c: v.round(6) for c, v in preds.items()}}
                         ).to_csv(PRED_DIR / f"{kind}_seed{seed}.csv", index=False)
            new = pd.DataFrame(rows)
            new["auc"] = new["auc"].round(6)
            if len(done):
                done = done[~((done["model"] == kind) & (done["seed"] == seed))]
            done = pd.concat([done, new], ignore_index=True)
            done.to_csv(out_csv, index=False)
            print(new[["model", "seed", "k", "population", "auc"]].to_string(index=False))
            print(f"{kind} seed {seed}: {info}, {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
