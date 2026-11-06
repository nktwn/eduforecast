"""Fact schema: every number the advisor may say comes from a Fact."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

STATUSES = ("проверено", "исследовательское", "демо", "нет данных")
# Reliability order: a statement is as reliable as its weakest fact.
RELIABILITY = {s: i for i, s in enumerate(STATUSES)}
MODULES = ("academic", "research", "finance", "aitu", "international", "upbringing", "digital", "system")
UNITS = {
    "auc": "AUC (0.5 — случайно, 1 — идеально)",
    "share": "доля",
    "gain": "выигрыш над эталоном",
    "pp": "п.п.",
    "count": "шт.",
    "kzt_thousand": "тыс. тенге",
    "ratio": "коэффициент",
    "brier": "Brier score",
    "p_value": "p-значение",
    "log": "логарифм",
    "text": "текст",
    "bool": "да/нет",
}
ID_RE = re.compile(r"^[a-z0-9_]+(\.[a-z0-9_]+)+$")


@dataclass
class Fact:
    id: str
    module: str
    metric: str          # human-readable name (Russian)
    value: float | int | str | bool | None
    unit: str
    period: str
    status: str
    source: str          # repository-relative path of the saved result file
    caveat: str
    built_at: str = ""
    group: str = ""      # e.g. faculty code, k, target
    attention: bool = False  # shown in "Что требует внимания"
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def validate_fact(f: Fact | dict) -> list[str]:
    d = f.to_dict() if isinstance(f, Fact) else f
    errors = []
    if not ID_RE.match(str(d.get("id", ""))):
        errors.append(f"bad id {d.get('id')!r}")
    for key in ("metric", "source", "caveat", "period", "status", "unit", "module"):
        if not str(d.get(key) or "").strip():
            errors.append(f"{d.get('id')}: empty {key}")
    if d.get("status") not in STATUSES:
        errors.append(f"{d.get('id')}: status {d.get('status')!r} not in {STATUSES}")
    if d.get("module") not in MODULES:
        errors.append(f"{d.get('id')}: module {d.get('module')!r}")
    if d.get("unit") not in UNITS:
        errors.append(f"{d.get('id')}: unit {d.get('unit')!r}")
    if d.get("status") != "нет данных" and d.get("value") is None:
        errors.append(f"{d.get('id')}: value missing but status is {d.get('status')!r}")
    if d.get("status") == "нет данных" and d.get("value") not in (None, ""):
        if not isinstance(d.get("value"), str):
            errors.append(f"{d.get('id')}: status 'нет данных' but numeric value")
    return errors


def validate_all(facts: list[Fact | dict]) -> list[str]:
    errors, seen = [], set()
    for f in facts:
        d = f.to_dict() if isinstance(f, Fact) else f
        if d["id"] in seen:
            errors.append(f"duplicate id {d['id']}")
        seen.add(d["id"])
        errors += validate_fact(d)
    return errors


def weakest(statuses: list[str]) -> str:
    return max(statuses, key=lambda s: RELIABILITY[s]) if statuses else "нет данных"
