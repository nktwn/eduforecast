import hashlib
from datetime import datetime, timezone
from typing import Protocol

import numpy as np
import pandas as pd

from src.finance.api import demo_model
from src.finance.api.contract import CONTRACT_VERSION, TARGET_META, flag
from src.finance.api.features import FEATURE_LABELS, FEATURES, build_frame, target_frame
from src.finance.config import PANEL_PATH, YEAR_MAX, YEAR_MIN
from src.finance.criterion import MIN_COHORT, PRICE_BASE_FY, TARGETS

HORIZON_YEAR = YEAR_MAX + 1
N_PEERS = 5
PEER_FEATURES = ["log_fte", "log_core_real", "retention_level", "grad_level", "instruction_share"]
COHORT_COLUMN = {"retention_rate": "retention_cohort", "grad_rate_150": "grad_cohort"}
OUTLIER_CHANGE = {"percentage_points": 20.0, "log_ratio": 0.5}
DATA_VINTAGE = {"source": "IPEDS Complete Data Files (NCES), выгрузка 2026-10-09", "first_year": YEAR_MIN,
                "last_year": YEAR_MAX, "price_base": f"CPI-U, доллары FY{PRICE_BASE_FY}"}


class Provider(Protocol):
    def search(self, query: str, limit: int = 20) -> list[dict]: ...

    def forecast(self, series_id: int) -> dict: ...


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _num(x):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) or pd.isna(x) else float(x)


class FinanceRepository:
    def __init__(self, panel: pd.DataFrame | None = None):
        self.panel = panel if panel is not None else pd.read_parquet(PANEL_PATH)
        self.frame = build_frame(self.panel)
        self.targets = {t: target_frame(self.frame, t) for t in TARGETS}
        latest = self.frame.sort_values("year").groupby("series_id").tail(1)
        self.directory = latest[["series_id", "unitid", "name", "state", "control_label", "carnegie_group",
                                 "peer_group", "year"]].rename(columns={"year": "last_year"}).reset_index(drop=True)
        self.directory["first_year"] = self.directory["series_id"].map(self.frame.groupby("series_id")["year"].min())

    def search(self, query: str, limit: int = 20) -> list[dict]:
        q = query.strip().lower()
        d = self.directory
        if q:
            mask = d["name"].str.lower().str.contains(q, regex=False) | (d["state"].str.lower() == q)
            if q.isdigit():
                mask |= (d["unitid"] == int(q)) | (d["series_id"] == int(q))
            d = d[mask]
        d = d.sort_values(["last_year", "name"], ascending=[False, True]).head(limit)
        return [{"series_id": int(r.series_id), "unitid": int(r.unitid), "name": r.name, "state": r.state,
                 "control": r.control_label, "carnegie_group": r.carnegie_group, "first_year": int(r.first_year),
                 "last_year": int(r.last_year)}
                for r in d.itertuples()]

    def rows(self, series_id: int) -> pd.DataFrame:
        return self.frame[self.frame["series_id"] == series_id].sort_values("year")

    def institution(self, series_id: int) -> dict:
        r = self.rows(series_id).iloc[-1]
        return {"unitid": int(r["unitid"]), "series_id": int(series_id), "name": r["name"], "state": r["state"],
                "control": r["control_label"], "carnegie_group": r["carnegie_group"], "peer_group": r["peer_group"]}

    def peers(self, series_id: int, n: int = N_PEERS) -> pd.DataFrame:
        rows = self.rows(series_id)
        year, group = int(rows["year"].iloc[-1]), rows["peer_group"].iloc[-1]
        pool = self.frame[self.frame["year"] == year].copy()
        x = pool[PEER_FEATURES]
        x = (x - x.mean()) / x.std()
        x = x.fillna(0.0)
        pool["distance"] = np.sqrt(((x - x[pool["series_id"] == series_id].iloc[0]) ** 2).sum(axis=1))
        same = pool[(pool["peer_group"] == group) & (pool["series_id"] != series_id)]
        if len(same) < n:
            same = pool[(pool["control"] == rows["control"].iloc[-1]) & (pool["series_id"] != series_id)]
        return same.nsmallest(n, "distance")

    def point_flags(self, r: pd.Series, target: str, value, change, change_scale: str) -> list[str]:
        codes = []
        if value is None:
            codes.append("MISSING_VALUE")
        if r["flag_covid"]:
            codes.append("COVID_YEAR")
        if r["flag_gasb75"] and target == "core_total_per_fte_real":
            codes.append("GASB75_2018")
        if r["id_transition"]:
            codes.append("ID_TRANSITION")
        if r["merger_absorption"]:
            codes.append("MERGER_ABSORPTION")
        cohort = COHORT_COLUMN.get(target)
        if cohort and value is not None and pd.notna(r[cohort]) and r[cohort] < MIN_COHORT:
            codes.append("SMALL_COHORT")
        if target == "core_total_per_fte_real":
            if r["prch_f"] == 1:
                codes.append("FINANCE_PARENT_CHILD")
            if r["finance_partial"]:
                codes.append("FINANCE_PARTIAL")
        if change is not None and abs(change) > OUTLIER_CHANGE[change_scale]:
            codes.append("OUTLIER_CHANGE")
        return codes

    def history(self, series_id: int, target: str) -> list[dict]:
        rows = self.rows(series_id)
        scale = TARGET_META[target]["change_scale"]
        out, prev = [], None
        for _, r in rows.iterrows():
            value = _num(r[target])
            if value is not None and target in ("fall_enrollment", "core_total_per_fte_real") and value <= 0:
                value = None
            change = None
            if value is not None and prev is not None and prev[0] == r["year"] - 1:
                change = np.log(value / prev[1]) if scale == "log_ratio" else value - prev[1]
            out.append({"year": int(r["year"]), "value": value,
                        "flags": self.point_flags(r, target, value, change, scale)})
            if value is not None:
                prev = (r["year"], value)
        return out

    def peer_median_history(self, peer_ids: list[int], target: str) -> list[dict]:
        p = self.frame[self.frame["series_id"].isin(peer_ids)]
        med = p.groupby("year")[target].median()
        return [{"year": int(y), "value": _num(v), "flags": ["COVID_YEAR"] if y in (2020, 2021, 2022) else []}
                for y, v in med.items()]

    def peer_records(self, peers: pd.DataFrame) -> list[dict]:
        return [{"unitid": int(r["unitid"]), "name": r["name"], "state": r["state"],
                 "distance": round(float(r["distance"]), 4),
                 "latest": {t: _num(r[t]) for t in TARGETS}} for _, r in peers.iterrows()]


def _to_level(last: float, change: float, scale: str) -> float:
    if scale == "log_ratio":
        return float(last * np.exp(change))
    return float(np.clip(last + change, 0.0, 100.0))


def _collect_flags(targets: list[dict], extra: list[dict]) -> list[dict]:
    flags = list(extra)
    seen = set()
    for t in targets:
        for point in t["history"]:
            for code in point["flags"]:
                if code in ("MISSING_VALUE",):
                    continue
                key = (code, point["year"], t["target"])
                if key not in seen:
                    seen.add(key)
                    flags.append(flag(code, year=point["year"], target=t["target"]))
        if not t["eligible"]:
            flags.append(flag("NOT_ELIGIBLE", target=t["target"], message=t["ineligible_reason"]))
    return flags


class DemoProvider:
    name = "demo-lightgbm"

    def __init__(self, repo: FinanceRepository | None = None):
        self.repo = repo or FinanceRepository()
        self.meta, self.boosters = demo_model.load()

    def search(self, query: str, limit: int = 20) -> list[dict]:
        return self.repo.search(query, limit)

    def _target_block(self, series_id: int, target: str, peer_ids: list[int]) -> dict:
        meta = TARGET_META[target]
        scale = meta["change_scale"]
        tf = self.repo.targets[target]
        rows = tf[tf["series_id"] == series_id].sort_values("year")
        last = rows.iloc[-1]
        block = {"target": target, "label": meta["label"], "unit": meta["unit"], "change_scale": scale,
                 "eligible": True, "ineligible_reason": None,
                 "history": self.repo.history(series_id, target), "forecast": None, "baselines": [],
                 "explanation": None, "peer_median_history": self.repo.peer_median_history(peer_ids, target)}
        last_value = _num(last["_t"])
        reason = None
        if int(last["year"]) != YEAR_MAX:
            reason = f"Ряд заканчивается в {int(last['year'])} году (вуз закрылся, слился или вышел из выборки)"
        elif last_value is None or (scale == "log_ratio" and last_value <= 0):
            spec = TARGETS[target]
            reason = ("Нет бакалавриата или когорта меньше 30 студентов" if spec["eligibility"]
                      else f"Нет значения за {YEAR_MAX} год")
        if reason:
            block.update({"eligible": False, "ineligible_reason": reason})
            return block

        x = rows[FEATURES].iloc[[-1]]
        booster = self.boosters[target]
        change = float(booster.predict(x)[0])
        contrib = booster.predict(x, pred_contrib=True)[0]
        q = self.meta["targets"][target]["interval_half_width"]
        block["forecast"] = {
            "year": HORIZON_YEAR, "value": _to_level(last_value, change, scale), "predicted_change": change,
            "interval": {"level": self.meta["interval_level"], "lower": _to_level(last_value, change - q, scale),
                         "upper": _to_level(last_value, change + q, scale),
                         "method": "split conformal (|остаток| на 2018 году)"},
        }
        group_change = _num(last["group_change"])
        block["baselines"] = [
            {"name": "naive", "value": last_value},
            {"name": "peer_group_mean_growth",
             "value": _to_level(last_value, group_change, scale) if group_change is not None else None},
        ]
        block["explanation"] = {
            "method": "TreeSHAP (LightGBM pred_contrib)", "scale": scale, "base_value": float(contrib[-1]),
            "prediction": change,
            "contributions": [{"feature": f, "label": FEATURE_LABELS[f], "feature_value": _num(x[f].iloc[0]),
                               "contribution": float(c)} for f, c in zip(FEATURES, contrib[:-1])],
        }
        return block

    def forecast(self, series_id: int) -> dict:
        peers = self.repo.peers(series_id)
        peer_ids = peers["series_id"].astype(int).tolist()
        targets = [self._target_block(series_id, t, peer_ids) for t in TARGETS]
        extra = [flag("DEMO_MODEL")]
        if len(self.repo.rows(series_id)) < 5:
            extra.append(flag("SHORT_HISTORY"))
        return {
            "contract_version": CONTRACT_VERSION, "generated_at": _now(),
            "provider": {"name": self.name, "is_mock": False, "is_demo": True,
                         "model_version": self.meta["version"],
                         "trained_through_year": self.meta["trained_through_year"],
                         "evaluated_against_criterion": False,
                         "notes": "LightGBM на изменение за год; обучение на целевых годах ≤2017, калибровка "
                                  "интервала на 2018; гиперпараметры не подбирались."},
            "institution": self.repo.institution(series_id), "data_vintage": DATA_VINTAGE,
            "horizon_year": HORIZON_YEAR, "targets": targets, "peers": self.repo.peer_records(peers),
            "data_quality": {"flags": _collect_flags(targets, extra)},
        }


class MockProvider:
    name = "mock"
    BASE = {"retention_rate": (78.0, 1.5), "grad_rate_150": (60.0, 1.8), "fall_enrollment": (8000.0, 0.03),
            "core_total_per_fte_real": (26000.0, 0.04)}

    def __init__(self, directory: list[dict] | None = None):
        self.directory = directory or [
            {"series_id": 900000 + i, "unitid": 900000 + i, "name": f"Mock University {i}", "state": "XX",
             "control": "public" if i % 2 else "private_nonprofit", "carnegie_group": "Master's L",
             "first_year": YEAR_MIN, "last_year": YEAR_MAX} for i in range(1, 11)]

    def search(self, query: str, limit: int = 20) -> list[dict]:
        q = query.strip().lower()
        return [d for d in self.directory if q in d["name"].lower()][:limit]

    def _rng(self, series_id: int, salt: str):
        seed = int(hashlib.sha1(f"{series_id}-{salt}".encode()).hexdigest()[:8], 16)
        return np.random.default_rng(seed)

    def forecast(self, series_id: int) -> dict:
        info = next((d for d in self.directory if d["series_id"] == series_id), None) or {
            "series_id": series_id, "unitid": series_id, "name": f"Mock University {series_id}", "state": "XX",
            "control": "public", "carnegie_group": "Master's L"}
        years = list(range(YEAR_MIN, YEAR_MAX + 1))
        targets, peers = [], []
        for target, (base, vol) in self.BASE.items():
            meta = TARGET_META[target]
            scale = meta["change_scale"]
            rng = self._rng(series_id, target)
            level = base * (1 + rng.normal(0, 0.1))
            values = []
            for _ in years:
                level = level + rng.normal(0, vol) if scale == "percentage_points" else level * np.exp(rng.normal(0.01, vol))
                values.append(round(float(level), 2))
            change = float(rng.normal(0, vol if scale == "percentage_points" else vol / 2))
            contributions = rng.normal(0, abs(change) / 3 + 1e-3, len(FEATURES))
            base_value = change - contributions.sum()
            q = 2 * vol if scale == "percentage_points" else 2 * vol
            last = values[-1]
            targets.append({
                "target": target, "label": meta["label"], "unit": meta["unit"], "change_scale": scale,
                "eligible": True, "ineligible_reason": None,
                "history": [{"year": y, "value": v, "flags": ["COVID_YEAR"] if y in (2020, 2021, 2022) else []}
                            for y, v in zip(years, values)],
                "forecast": {"year": HORIZON_YEAR, "value": _to_level(last, change, scale),
                             "predicted_change": change,
                             "interval": {"level": 0.8, "lower": _to_level(last, change - q, scale),
                                          "upper": _to_level(last, change + q, scale), "method": "mock"}},
                "baselines": [{"name": "naive", "value": last},
                              {"name": "peer_group_mean_growth", "value": _to_level(last, change / 2, scale)}],
                "explanation": {"method": "mock", "scale": scale, "base_value": float(base_value),
                                "prediction": change,
                                "contributions": [{"feature": f, "label": FEATURE_LABELS[f], "feature_value": None,
                                                   "contribution": float(c)} for f, c in zip(FEATURES, contributions)]},
                "peer_median_history": [{"year": y, "value": round(v * (1 + rng.normal(0, 0.03)), 2), "flags": []}
                                        for y, v in zip(years, values)],
            })
        for d in [x for x in self.directory if x["series_id"] != series_id][:N_PEERS]:
            peers.append({"unitid": d["unitid"], "name": d["name"], "state": d["state"],
                          "distance": round(float(self._rng(d["series_id"], "dist").uniform(0.2, 2.0)), 4),
                          "latest": {t: None for t in TARGETS}})
        return {
            "contract_version": CONTRACT_VERSION, "generated_at": _now(),
            "provider": {"name": self.name, "is_mock": True, "is_demo": True, "model_version": "mock-0.1",
                         "trained_through_year": None, "evaluated_against_criterion": False,
                         "notes": "Синтетические значения для разработки интерфейса."},
            "institution": {"unitid": info["unitid"], "series_id": info["series_id"], "name": info["name"],
                            "state": info["state"], "control": info["control"],
                            "carnegie_group": info["carnegie_group"], "peer_group": f"{info['control']} | {info['carnegie_group']}"},
            "data_vintage": {**DATA_VINTAGE, "source": "mock"},
            "horizon_year": HORIZON_YEAR, "targets": targets, "peers": peers,
            "data_quality": {"flags": [flag("MOCK_DATA")] + [flag("COVID_YEAR", year=y) for y in (2020, 2021, 2022)]},
        }
