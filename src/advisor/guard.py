"""Question pre-checks with deterministic answers (no LLM): individuals, small groups, modules without data,
budget percentages. Also flags attempts to override the rules."""
from __future__ import annotations

import re

STUDENT = re.compile(r"(студент\w*\s+(№\s*|id\s*|ид\s*)?\d{3,}|\bid\s*[:#№]?\s*\d{4,}|конкретн\w+\s+студент|"
                     r"(отчислить|исключить|наказать)\s+(ли\s+)?(студент|его|её|ее)|студент\w*\s+[А-ЯЁ][а-яё]+(ов|ев|ин|"
                     r"ова|ева|ина|ий|ая)\b|по фамилии)", re.IGNORECASE)
SMALL_GROUP = re.compile(r"групп\w*\s+из\s+(\d+)", re.IGNORECASE)
UPBRINGING = re.compile(r"(воспитат|внеучеб|куратор\w* встреч|общежит|волонт|дисциплинар)", re.IGNORECASE)
INTERNATIONAL = re.compile(r"(интернационализ|международн\w+\s+модул|мобильност|иностранн\w+\s+студент|двойн\w+\s+диплом|партн[её]рств|"
                           r"международн\w+\s+рейтинг|обмен\w*\s+студент)", re.IGNORECASE)
BUDGET_PCT = re.compile(r"(на\s+сколько\s+процент|сколько\s+процент|какой\s+процент|какую\s+долю|%)", re.IGNORECASE)
BUDGET_WORDS = re.compile(r"(бюджет|расход|финансир|затрат|выдел|перераспредел)", re.IGNORECASE)
OVERRIDE = re.compile(r"(игнорир\w*\s+(все\s+)?(правил|инструкц)|забудь\s+(правил|инструкц)|ignore\s+(all\s+)?"
                      r"(previous|the)?\s*(rules|instructions)|без\s+плейсхолдер|выдумай|придумай\s+(цифр|числ)|"
                      r"system prompt|системн\w+ промпт)", re.IGNORECASE)


def classify(question: str) -> list[str]:
    q = question or ""
    tags = []
    if STUDENT.search(q):
        tags.append("individual")
    m = SMALL_GROUP.search(q)
    if m and int(m.group(1)) < 30:
        tags.append("small_group")
    if UPBRINGING.search(q):
        tags.append("upbringing")
    if INTERNATIONAL.search(q):
        tags.append("international")
    if BUDGET_PCT.search(q) and BUDGET_WORDS.search(q):
        tags.append("budget_percent")
    if OVERRIDE.search(q):
        tags.append("override_attempt")
    return tags


def deterministic_answer(tags: list[str]) -> dict | None:
    """Answer in the advisor JSON schema (placeholders only), or None to go to the LLM."""
    if "individual" in tags:
        return {"observation": ("Советник не выносит суждений и решений по отдельным студентам и видит только "
                                "агрегаты групп не меньше тридцати человек."),
                "basis": [], "recommendation": ("Список студентов с риском и главными причинами — на странице "
                                                "«Академический → Студенты»; решение принимает куратор после беседы."),
                "risks": "Модель риска оценена на демо-данных и не годится для решений о конкретном человеке."}
    if "small_group" in tags:
        return {"observation": "Статистика по группам меньше тридцати студентов не показывается.",
                "basis": [], "recommendation": "Задайте вопрос по факультету целиком или по группе риска.",
                "risks": "Маленькие группы позволяют узнать отдельных людей, а их показатели нестабильны."}
    if "upbringing" in tags:
        return {"no_data": True,
                "observation": "Воспитательный модуль: {fact:system.module.upbringing.status}.",
                "basis": ["system.module.upbringing.status", "system.needed_data.upbringing"],
                "needed_data": "{fact:system.needed_data.upbringing}",
                "recommendation": "Рекомендаций нет: сначала нужно собрать данные.",
                "risks": "Любые числа по этому направлению были бы выдуманными."}
    if "international" in tags:
        return {"no_data": True,
                "observation": ("Международный модуль: {fact:system.module.international.status}. Есть только доля "
                                "международных соавторств на панели вузов; модели для неё не лучше naive "
                                "({fact:research.panel.intl_collab_share.passed})."),
                "basis": ["system.module.international.status", "system.needed_data.international",
                          "research.panel.intl_collab_share.passed"],
                "needed_data": "{fact:system.needed_data.international}",
                "recommendation": "Рекомендаций по интернационализации нет: сначала нужно собрать данные.",
                "risks": "Доля соавторств не описывает мобильность, иностранных студентов и партнёрства."}
    if "budget_percent" in tags:
        return {"observation": ("Рекомендаций по бюджету в процентах советник не даёт. Есть только описательные "
                                "ориентиры: медианная доля оплаты труда у аналогов США "
                                "{fact:aitu.us_peers.compensation_share_vs_us_peers.p50} против "
                                "{fact:aitu.y2020.share_payroll_with_social_in_expenses.excl_one_off} у AITU без "
                                "разовой статьи; связь доли студенческих сервисов с retention: {fact:finance.h1.verdict}."),
                "basis": ["aitu.us_peers.compensation_share_vs_us_peers.p50",
                          "aitu.y2020.share_payroll_with_social_in_expenses.excl_one_off", "finance.h1.verdict"],
                "recommendation": ("Решения о долях расходов принимать по данным и стратегии вуза; бенчмарк США "
                                   "использовать только как контекст."),
                "risks": "Данные США, контекст другой; связь не означает причинного влияния."}
    return None
