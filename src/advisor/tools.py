"""Advisor tools (function calling). Each returns facts with status, caveat, source and a {fact:ID} token."""
from __future__ import annotations

from src.advisor.facts.registry import Registry

FACULTIES = ["all", "aaa", "bbb", "ccc", "ddd", "eee", "fff", "ggg"]


def fact_view(reg: Registry, f: dict, caveat_no: int) -> dict:
    return {"placeholder": "{fact:" + f["id"] + "}", "metric": f["metric"], "value": reg.display(f["id"]),
            "status": f["status"], "period": f["period"], "caveat": caveat_no}


def _views(reg: Registry, facts: list[dict]) -> dict:
    """Compact payload: caveats are listed once and referenced by number (keeps requests small)."""
    caveats: list[str] = []
    out = []
    for f in facts:
        if f["caveat"] not in caveats:
            caveats.append(f["caveat"])
        out.append(fact_view(reg, f, caveats.index(f["caveat"]) + 1))
    return {"facts": out, "caveats": {i + 1: c for i, c in enumerate(caveats)}, "ids": [f["id"] for f in facts]}


def academic_overview(reg: Registry, k: int = 5, faculty: str = "all") -> dict:
    k = k if k in (5, 10, 20) else 5
    faculty = faculty.lower() if faculty.lower() in FACULTIES else "all"
    facts = reg.select(prefix=f"academic.risk.k{k}.{faculty}.")
    facts += reg.select(prefix=f"academic.audit.rf.k{k}.")
    facts += [reg.get("academic.risk.before.all.auc")]
    return _views(reg, [f for f in facts if f])


def risk_groups(reg: Registry, k: int = 5, faculty: str = "all") -> dict:
    k = k if k in (5, 10, 20) else 5
    faculty = faculty.lower() if faculty.lower() in FACULTIES else "all"
    facts = reg.select(prefix=f"academic.riskgroup.k{k}.{faculty}.")
    facts += [reg.get(f"academic.risk.k{k}.{faculty}.base_rate")]
    return _views(reg, [f for f in facts if f])


def research_overview(reg: Registry) -> dict:
    facts = [f for f in reg.select(prefix="research.panel.") if not f["id"].endswith(".best_model")]
    facts += reg.select(prefix="research.aitu.")
    facts += [reg.get("system.capability.research.cannot")]
    return _views(reg, [f for f in facts if f])


AITU_KEY = ("share_state_order_in_revenue", "share_paid_tuition_in_revenue", "largest_revenue_source_share",
            "share_payroll_with_social_in_expenses", "share_depreciation_in_expenses", "share_interest_in_expenses",
            "current_ratio", "liabilities_to_assets", "equity", "revenue_per_employee_thousand_kzt")


def aitu_finance_profile(reg: Registry, variant: str = "both") -> dict:
    """2020 snapshot: key ratios (both expense variants), rule flags, position among US peers."""
    facts = [f for f in reg.select(prefix="aitu.y2020.") if f["id"].split(".")[2] in AITU_KEY]
    if variant == "all":
        facts = [f for f in facts if not f["id"].endswith(".excl_one_off")]
    elif variant == "excl_one_off":
        facts = [f for f in facts if f["id"].endswith(".excl_one_off") or "_in_expenses" not in f["id"]]
    facts += [f for f in reg.select(prefix="aitu.rule.") if f["value"] is not None]
    facts += reg.select(prefix="aitu.position.")
    facts += [reg.get("aitu.y2019.current_ratio"), reg.get("aitu.y2019.equity")]
    return _views(reg, [f for f in facts if f])


def finance_benchmark(reg: Registry) -> dict:
    facts = [f for f in reg.select(prefix="aitu.us_peers.") if not f["id"].endswith(".n")]
    facts += [f for f in reg.select(prefix="finance.h") if not f["id"].endswith(("ci_lo", "ci_hi"))]
    return _views(reg, facts)


def finance_models(reg: Registry) -> dict:
    facts = [f for f in reg.select(prefix="finance.criterion.")]
    facts += reg.select(prefix="finance.unseen.") + reg.select(prefix="finance.interval.")
    facts += reg.select(prefix="finance.ma3.")
    return _views(reg, facts)


def module_status(reg: Registry) -> dict:
    return _views(reg, reg.select(prefix="system.module.") + reg.select(prefix="system.needed_data."))


def capability_matrix(reg: Registry) -> dict:
    return _views(reg, reg.select(prefix="system.capability."))


IMPLEMENTATIONS = {
    "academic_overview": academic_overview, "risk_groups": risk_groups, "research_overview": research_overview,
    "aitu_finance_profile": aitu_finance_profile, "finance_benchmark": finance_benchmark,
    "finance_models": finance_models,
    "module_status": module_status, "capability_matrix": capability_matrix,
}
_K = {"type": "integer", "enum": [5, 10, 20], "description": "неделя прогноза k"}
_FAC = {"type": "string", "enum": FACULTIES, "description": "код факультета (условный, OULAD) или all"}
SCHEMAS = {
    "academic_overview": ("Качество модели риска отчисления на неделе k (демо-данные OULAD) и аудит модели",
                          {"k": _K, "faculty": _FAC}),
    "risk_groups": ("Агрегаты группы высокого риска (топ-10%, не меньше 30 студентов)", {"k": _K, "faculty": _FAC}),
    "research_overview": ("Публикации AITU (OpenAlex), иллюстративный прогноз, модели роста на панели вузов", {}),
    "aitu_finance_profile": ("Финансовый профиль AITU 2019–2020 (снимок, PDF) и флаги правил",
                             {"variant": {"type": "string", "enum": ["both", "all", "excl_one_off"]}}),
    "finance_benchmark": ("Аналоги США: перцентили долей расходов; гипотезы H1–H4 о связи структуры бюджета и "
                          "результатов (связь, не эффект)", {}),
    "finance_models": ("Проверка моделей Finance (данные США): критерий по 4 целям, невиданные вузы, покрытие "
                       "интервалов, сравнение со скользящим средним", {}),
    "module_status": ("Статус модулей системы и какие данные нужно собрать", {}),
    "capability_matrix": ("Что система умеет и чего не умеет по направлениям", {}),
}


def tool_specs(names: tuple[str, ...]) -> list[dict]:
    return [{"type": "function", "function": {"name": n, "description": SCHEMAS[n][0],
                                              "parameters": {"type": "object", "properties": SCHEMAS[n][1]}}}
            for n in names]


def call(reg: Registry, name: str, args: dict, allowed: tuple[str, ...]) -> dict:
    if name not in allowed:
        return {"error": f"инструмент {name} недоступен для этой роли", "facts": []}
    params = SCHEMAS[name][1]
    clean = {k: v for k, v in (args or {}).items() if k in params}
    return IMPLEMENTATIONS[name](reg, **clean)
