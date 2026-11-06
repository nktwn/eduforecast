"""Persisted results of heavy app computations (scripts/prepare_app.py). Not in git.

An entry is used only if its signature (sizes and modification times of the source files, plus a
code version) matches; otherwise the page computes as before. The computation is the same function.
"""
from __future__ import annotations

import hashlib
import json
import pickle
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = ROOT / "data" / "app_cache"
CODE_VERSION = "2026-10-16.1"
OULAD_FILES = ["studentInfo.csv", "studentVle.csv", "studentAssessment.csv", "assessments.csv",
               "studentRegistration.csv"]


def _sig(paths: list[Path]) -> str:
    parts = [CODE_VERSION] + [f"{p.name}:{p.stat().st_size}:{int(p.stat().st_mtime)}" if p.exists() else
                              f"{p.name}:missing" for p in paths]
    return hashlib.sha1("|".join(parts).encode()).hexdigest()


def oulad_signature() -> str:
    return _sig([ROOT / "data" / "raw" / f for f in OULAD_FILES] + [ROOT / "app" / "components" / "risk_model.py"])


def research_signature() -> str:
    return _sig([ROOT / "data" / "research" / "raw" / "yearly_work_counts_I4405257690.json",
                 ROOT / "src" / "research" / "forecast.py"])


def load(name: str, signature: str):
    meta_path = CACHE_DIR / "meta.json"
    path = CACHE_DIR / f"{name}.pkl"
    if not (meta_path.exists() and path.exists()):
        return None
    try:
        meta = json.loads(meta_path.read_text())
        if meta.get(name) != signature:
            return None
        with path.open("rb") as fh:
            return pickle.load(fh)
    except (OSError, ValueError, pickle.UnpicklingError, EOFError, AttributeError, ModuleNotFoundError):
        return None


def save(name: str, signature: str, obj) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with (CACHE_DIR / f"{name}.pkl").open("wb") as fh:
        pickle.dump(obj, fh, protocol=pickle.HIGHEST_PROTOCOL)
    meta_path = CACHE_DIR / "meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    meta[name] = signature
    meta_path.write_text(json.dumps(meta, indent=1))
