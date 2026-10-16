"""Roles: which modules and tools a role sees, its tone, quick questions."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Role:
    id: str
    name: str
    modules: tuple[str, ...]
    tools: tuple[str, ...]
    tone: str
    quick_questions: tuple[str, ...] = field(default_factory=tuple)


COMMON_TOOLS = ("module_status", "capability_matrix")

ROLES = {
    "rector": Role(
        "rector", "Ректор", ("academic", "research", "finance", "aitu", "international", "upbringing", "digital"),
        ("academic_overview", "risk_groups", "research_overview", "aitu_finance_profile", "finance_benchmark",
         "finance_models")
        + COMMON_TOOLS,
        "Кратко и по существу, на уровне вуза: 3–5 главных наблюдений, что проверено и что нет.",
        ("Что сейчас требует внимания по всем направлениям?", "Каким результатам системы можно доверять?",
         "Каково финансовое положение AITU по отчётности 2020 года?")),
    "vp_academic": Role(
        "vp_academic", "Проректор по академической работе", ("academic",),
        ("academic_overview", "risk_groups") + COMMON_TOOLS,
        "Предметно об успеваемости и отчислениях; только агрегаты групп не меньше 30 студентов.",
        ("Насколько точна модель риска на неделе 5?", "Как меняется качество модели с неделей k?",
         "Какой факультет требует внимания по риску отчисления?")),
    "vp_research": Role(
        "vp_research", "Проректор по науке и инновациям", ("research",),
        ("research_overview",) + COMMON_TOOLS,
        "О публикационной активности: счётчики и доли раздельно, прогнозы — с оговорками.",
        ("Как растёт число публикаций AITU?", "Каким прогнозам научной активности можно доверять?",
         "Что известно о международном соавторстве?")),
    "vp_finance": Role(
        "vp_finance", "Проректор по экономике и финансам", ("finance", "aitu"),
        ("aitu_finance_profile", "finance_benchmark", "finance_models") + COMMON_TOOLS,
        "О структуре доходов и расходов; сравнения с США — только структурные доли, без сумм.",
        ("Как структура расходов AITU выглядит на фоне аналогов?",
         "Связана ли доля расходов на студенческие сервисы с retention?",
         "Прошли ли финансовые модели проверку?")),
    "vp_international": Role(
        "vp_international", "Проректор по интернационализации", ("international",),
        ("research_overview",) + COMMON_TOOLS,
        "О международной деятельности; для отсутствующих данных — что нужно собрать.",
        ("Что известно об интернационализации AITU?", "Каких данных не хватает для международного модуля?")),
    "vp_digital": Role(
        "vp_digital", "Проректор по цифровизации", ("digital",),
        COMMON_TOOLS,
        "О готовности данных и моделей системы, о том, что нужно собрать.",
        ("Какие модули системы готовы, а какие нет?", "Каких данных не хватает системе?")),
}
DEFAULT_ROLE = "rector"
