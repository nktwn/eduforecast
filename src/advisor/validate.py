"""Answer schema, validation and rendering. Numbers reach the user only through {fact:ID}."""
from __future__ import annotations

import json
import re

from src.advisor.facts.registry import Registry
from src.advisor.facts.schema import weakest

PLACEHOLDER = re.compile(r"\{fact:([a-z0-9_.]+)\}")
TEXT_FIELDS = ("observation", "recommendation", "risks", "needed_data")
REQUIRED = ("observation", "basis", "recommendation", "risks")
# Causal wording is forbidden: results are associations or forecasts, not effects.
CAUSAL = re.compile(r"(эффект|привед[её]т|приводит к|вызов[её]т|повлеч[её]т|гарантир|обеспечит|повысит|снизит|"
                    r"увеличит|уменьшит|улучшит|ухудшит|благодаря чему|в результате чего|потому что доля)",
                    re.IGNORECASE)
# Numbers that are allowed without a placeholder: years, percentiles, hypothesis/feature-set names,
# k values, list numbering.
ALLOWED_NUMBER = re.compile(r"(\b(19|20)\d{2}\b|\bP(10|25|50|75|90)\b|\bH[1-4]\b|\bS[1-3]\b|"
                            r"\bk\s*=\s*(5|10|20)\b|недел[а-яё]*\s+(5|10|20)\b|^\s*\d+[.)]\s)", re.MULTILINE)
DIGIT = re.compile(r"\d+(?:[.,]\d+)?")


def parse(content: str | None) -> dict | None:
    if not content:
        return None
    text = content.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        return None
    try:
        obj = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def _numbers_in(text: str) -> set[str]:
    return {m.group(0).replace(",", ".") for m in DIGIT.finditer(text)}


def allowed_numbers(reg: Registry, fact_ids: set[str]) -> set[str]:
    """Numbers appearing in the names and periods of the facts the model was given."""
    out = set()
    for fid in fact_ids:
        f = reg.get(fid)
        if f:
            out |= _numbers_in(f["metric"]) | _numbers_in(f["period"])
    return out


def check(answer: dict | None, reg: Registry, allowed_ids: set[str]) -> list[str]:
    if answer is None:
        return ["ответ не является JSON-объектом"]
    errors = []
    for key in REQUIRED:
        if key not in answer:
            errors.append(f"нет поля {key}")
    if errors:
        return errors
    if not isinstance(answer["basis"], list):
        errors.append("basis должен быть списком id фактов")
    ok_numbers = allowed_numbers(reg, allowed_ids)
    for key in TEXT_FIELDS:
        text = answer.get(key) or ""
        if not isinstance(text, str):
            errors.append(f"{key} должен быть строкой")
            continue
        for fid in PLACEHOLDER.findall(text):
            if reg.get(fid) is None:
                errors.append(f"неизвестный плейсхолдер {{fact:{fid}}}")
            elif fid not in allowed_ids:
                errors.append(f"факт {fid} не получен из инструментов в этом запросе")
        if key == "recommendation" and PLACEHOLDER.search(text):
            errors.append("в рекомендации не должно быть чисел, даже из фактов")
        bare = ALLOWED_NUMBER.sub(" ", PLACEHOLDER.sub(" ", text))
        bad = sorted(n for n in _numbers_in(bare) if n not in ok_numbers or key == "recommendation")
        if bad:
            errors.append(f"число без плейсхолдера в {key}: {', '.join(bad[:5])}")
        if CAUSAL.search(text):
            errors.append(f"причинная формулировка в {key}: «{CAUSAL.search(text).group(0)}» — нужна «связь»")
    for fid in answer.get("basis") or []:
        if not isinstance(fid, str) or reg.get(fid) is None:
            errors.append(f"неизвестный факт в basis: {fid}")
        elif fid not in allowed_ids:
            errors.append(f"факт {fid} в basis не получен из инструментов")
    return errors


def used_fact_ids(answer: dict) -> list[str]:
    ids = list(answer.get("basis") or [])
    for key in TEXT_FIELDS:
        for fid in PLACEHOLDER.findall(answer.get(key) or ""):
            if fid not in ids:
                ids.append(fid)
    return ids


def render_text(text: str, reg: Registry) -> str:
    return PLACEHOLDER.sub(lambda m: reg.display(m.group(1)), text or "")


def render(answer: dict, reg: Registry) -> dict:
    ids = [i for i in used_fact_ids(answer) if reg.get(i)]
    facts = [reg.get(i) for i in ids]
    statuses = [f["status"] for f in facts]
    reliability = weakest(statuses) if statuses else "нет данных"
    weak = sorted({s for s in statuses if s in ("исследовательское", "демо", "нет данных")})
    return {
        "observation": render_text(answer["observation"], reg),
        "recommendation": render_text(answer["recommendation"], reg),
        "risks": render_text(answer["risks"], reg),
        "needed_data": render_text(answer.get("needed_data", ""), reg),
        "no_data": bool(answer.get("no_data")),
        "facts": facts,
        "reliability": reliability,
        "warning": (f"Ответ опирается на факты со статусом: {', '.join(weak)}. Проверьте оговорки в «Основаниях»."
                    if weak else ""),
    }
