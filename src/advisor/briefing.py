"""Offline briefing by role: templates + facts, no LLM. Every card passes the same validation."""
from __future__ import annotations

from datetime import datetime

from src.advisor.facts.registry import Registry
from src.advisor.roles import ROLES
from src.advisor.validate import PLACEHOLDER, check, render

TARGETS = {"retention_rate": "retention первокурсников", "grad_rate_150": "выпускаемость",
           "fall_enrollment": "приём", "core_total_per_fte_real": "core-расходы на FTE"}


def _val(reg, fid):
    f = reg.get(fid)
    return None if f is None else f["value"]


def card_academic(reg: Registry, k: int = 5) -> dict:
    return {"title": "Модель раннего предупреждения отчислений",
            "observation": (f"На неделе k = {k} модель риска различает будущих ушедших с AUC {{fact:academic.risk.k{k}"
                            f".all.auc}}; в группе высокого риска (топ-10%) реально ушли "
                            f"{{fact:academic.risk.k{k}.all.precision_top10}}, это {{fact:academic.risk.k{k}.all."
                            f"recall_top10}} всех ушедших. Прежняя оценка на обучающих данных была завышена: "
                            "AUC {fact:academic.risk.before.all.auc}."),
            "basis": [f"academic.risk.k{k}.all.auc", f"academic.risk.k{k}.all.precision_top10",
                      f"academic.risk.k{k}.all.recall_top10", "academic.risk.before.all.auc"],
            "recommendation": ("Использовать список риска для приоритизации внимания кураторов, а не для решений о "
                               "конкретных студентах; до внедрения проверить модель на данных LMS AITU."),
            "risks": ("Данные — демо-набор OULAD с условными факультетами; на данных AITU модель не проверялась. "
                      "AUC умеренный: группа высокого риска означает «выше среднего», а не «уйдёт».")}


def card_academic_k(reg: Registry) -> dict:
    return {"title": "Качество модели по неделям",
            "observation": ("AUC модели риска растёт с неделей прогноза: {fact:academic.risk.k5.all.auc} на неделе 5, "
                            "{fact:academic.risk.k10.all.auc} на неделе 10, {fact:academic.risk.k20.all.auc} на "
                            "неделе 20; доля ушедших среди ещё учащихся при этом падает до "
                            "{fact:academic.risk.k20.all.base_rate}."),
            "basis": ["academic.risk.k5.all.auc", "academic.risk.k10.all.auc", "academic.risk.k20.all.auc",
                      "academic.risk.k20.all.base_rate"],
            "recommendation": "Раннее предупреждение ценнее, но менее точно: сочетать модель с беседой куратора.",
            "risks": "Оценка на демо-данных OULAD; факультеты условные."}


def card_research(reg: Registry) -> dict:
    return {"title": "Научная активность",
            "observation": ("Публикаций AITU в OpenAlex: {fact:research.aitu.works.y2023} в 2023, "
                            "{fact:research.aitu.works.y2024} в 2024, {fact:research.aitu.works.y2025} в 2025. На "
                            "панели вузов Казахстана модели лучше naive для числа публикаций "
                            "({fact:research.panel.works_count.best_gain}) и авторов "
                            "({fact:research.panel.unique_authors.best_gain}); для доли международных соавторств "
                            "критерий не пройден ({fact:research.panel.intl_collab_share.passed})."),
            "basis": ["research.aitu.works.y2023", "research.aitu.works.y2024", "research.aitu.works.y2025",
                      "research.panel.works_count.best_gain", "research.panel.unique_authors.best_gain",
                      "research.panel.intl_collab_share.passed"],
            "recommendation": ("Опираться на прогнозы счётчиков (публикации, авторы) как на ориентир; для долей "
                               "(международное соавторство, высокоцитируемые работы) использовать только описательную динамику."),
            "risks": "OpenAlex учитывает не все публикации; текущий год неполный."}


def card_research_forecast(reg: Registry) -> dict:
    return {"title": "Пример прогноза публикаций AITU (иллюстрация)",
            "observation": ("Проверка на 2025 году по данным до 2024: факт {fact:research.aitu.backtest2025.actual}, "
                            "логистический рост дал {fact:research.aitu.backtest2025.logistic_pred} (ошибка "
                            "{fact:research.aitu.backtest2025.logistic_error}), линейный — "
                            "{fact:research.aitu.backtest2025.linear_pred} (ошибка "
                            "{fact:research.aitu.backtest2025.linear_error})."),
            "basis": ["research.aitu.backtest2025.actual", "research.aitu.backtest2025.logistic_pred",
                      "research.aitu.backtest2025.logistic_error", "research.aitu.backtest2025.linear_pred",
                      "research.aitu.backtest2025.linear_error"],
            "recommendation": "Не использовать этот прогноз для плановых показателей: это иллюстрация метода.",
            "risks": "Proof-of-concept на нескольких годовых точках, проверка на одном году."}


def card_aitu(reg: Registry) -> dict:
    return {"title": "Финансовый профиль AITU (снимок 2020 года)",
            "observation": ("Госзаказ составил {fact:aitu.y2020.share_state_order_in_revenue} доходов; коэффициент "
                            "текущей ликвидности {fact:aitu.y2020.current_ratio}, капитал "
                            "{fact:aitu.y2020.equity}. Доля оплаты труда с соцотчислениями — "
                            "{fact:aitu.y2020.share_payroll_with_social_in_expenses} всех расходов и "
                            "{fact:aitu.y2020.share_payroll_with_social_in_expenses.excl_one_off} без разовой статьи "
                            "возмещения; медиана у аналогов США "
                            "{fact:aitu.us_peers.compensation_share_vs_us_peers.p50}."),
            "basis": ["aitu.y2020.share_state_order_in_revenue", "aitu.y2020.current_ratio", "aitu.y2020.equity",
                      "aitu.y2020.share_payroll_with_social_in_expenses",
                      "aitu.y2020.share_payroll_with_social_in_expenses.excl_one_off",
                      "aitu.us_peers.compensation_share_vs_us_peers.p50"],
            "recommendation": ("Сверить цифры с оригиналом отчётности и добавить годы 2021–2025, прежде чем делать "
                               "выводы; обсудить зависимость от одного источника дохода и ликвидность."),
            "risks": ("Цифры с отсканированного PDF, не сверены; два года отчётности; сравнение с США — только "
                      "структурные доли, контекст другой.")}


def card_finance_models(reg: Registry) -> dict:
    passed = [TARGETS[t] for t in TARGETS if _val(reg, f"finance.criterion.{t}.passed")]
    return {"title": "Проверка финансовых моделей (данные США)",
            "observation": ("Основная модель лучше naive, но не на зафиксированный порог в обеих оценках: retention "
                            "{fact:finance.criterion.retention_rate.all_years.gain} и "
                            "{fact:finance.criterion.retention_rate.excluding_flagged.gain}, выпускаемость "
                            "{fact:finance.criterion.grad_rate_150.excluding_flagged.gain}, приём "
                            "{fact:finance.criterion.fall_enrollment.excluding_flagged.gain}, расходы "
                            "{fact:finance.criterion.core_total_per_fte_real.excluding_flagged.gain}. Критерий пройден: "
                            + (", ".join(passed) if passed else "ни по одной цели") + "."),
            "basis": [f"finance.criterion.{t}.passed" for t in TARGETS] + [
                "finance.criterion.retention_rate.all_years.gain",
                "finance.criterion.retention_rate.excluding_flagged.gain",
                "finance.criterion.grad_rate_150.excluding_flagged.gain",
                "finance.criterion.fall_enrollment.excluding_flagged.gain",
                "finance.criterion.core_total_per_fte_real.excluding_flagged.gain"],
            "recommendation": "Использовать прогнозы Finance как ориентир с интервалом, а не как плановые цифры.",
            "risks": "Данные США (IPEDS), контекст другой; для AITU эти модели не применимы напрямую."}


def card_hypotheses(reg: Registry) -> dict:
    return {"title": "Структура бюджета и результаты (связь, не причина)",
            "observation": ("Связь доли студенческих сервисов с retention: {fact:finance.h1.verdict} (p с поправкой "
                            "Холма {fact:finance.h1.p_holm}); доли преподавания с выпускаемостью: "
                            "{fact:finance.h2.verdict}; академической поддержки с retention: {fact:finance.h3.verdict}; "
                            "институциональной поддержки с выпускаемостью: {fact:finance.h4.verdict}."),
            "basis": ["finance.h1.verdict", "finance.h1.p_holm", "finance.h2.verdict", "finance.h3.verdict",
                      "finance.h4.verdict"],
            "recommendation": ("Не обосновывать перераспределение бюджета этими данными; решения о долях расходов "
                               "принимать по собственным данным вуза и экспертно."),
            "risks": "Наблюдательные данные США; связь не означает причинного влияния."}


def card_modules(reg: Registry) -> dict:
    return {"title": "Готовность модулей",
            "observation": ("Академический: {fact:system.module.academic.status}; научный: "
                            "{fact:system.module.research.status}; финансы: {fact:system.module.finance.status}; "
                            "интернационализация: {fact:system.module.international.status}; воспитательный: "
                            "{fact:system.module.upbringing.status}; цифровизация: {fact:system.module.digital.status}."),
            "basis": [f"system.module.{m}.status" for m in ("academic", "research", "finance", "international",
                                                           "upbringing", "digital")],
            "recommendation": "Начать сбор данных для модулей без данных; приоритет — данные LMS AITU для риска.",
            "risks": "Статусы отражают состояние кода и сохранённых результатов."}


def card_no_data(reg: Registry, module: str, title: str) -> dict:
    return {"title": title, "no_data": True,
            "observation": f"Модуль не реализован: {{fact:system.module.{module}.status}}.",
            "basis": [f"system.module.{module}.status", f"system.needed_data.{module}"],
            "needed_data": f"{{fact:system.needed_data.{module}}}",
            "recommendation": "Рекомендаций нет: сначала нужно собрать данные.",
            "risks": "Любые числа по этому направлению были бы выдуманными."}


def card_international(reg: Registry) -> dict:
    card = card_no_data(reg, "international", "Интернационализация")
    card["observation"] += (" Единственный связанный показатель — доля международных соавторств на панели вузов: "
                            "модели для неё не лучше naive ({fact:research.panel.intl_collab_share.passed}).")
    card["basis"].append("research.panel.intl_collab_share.passed")
    return card


ROLE_CARDS = {
    "rector": [card_modules, card_academic, card_research, card_aitu, card_finance_models, card_hypotheses,
               lambda r: card_no_data(r, "upbringing", "Воспитательная работа"), card_international],
    "vp_academic": [card_academic, card_academic_k, card_modules],
    "vp_research": [card_research, card_research_forecast],
    "vp_finance": [card_aitu, card_finance_models, card_hypotheses],
    "vp_international": [card_international],
    "vp_digital": [card_modules, lambda r: card_no_data(r, "digital", "Цифровизация")],
}


def build(reg: Registry, role_id: str, k: int = 5) -> list[dict]:
    cards = []
    for fn in ROLE_CARDS[role_id]:
        card = fn(reg, k) if fn is card_academic else fn(reg)
        ids = set(card["basis"])
        for key in ("observation", "needed_data"):
            ids |= set(PLACEHOLDER.findall(card.get(key, "")))
        errors = check(card, reg, ids)
        if errors:
            raise ValueError(f"briefing card {card['title']!r} invalid: {errors}")
        cards.append({"title": card["title"], **render(card, reg)})
    return cards


def to_markdown(cards: list[dict], role_id: str, built_at: str | None) -> str:
    lines = [f"# Брифинг: {ROLES[role_id].name}", "",
             f"Сформирован {datetime.now():%d.%m.%Y %H:%M} по реестру фактов от {built_at or '—'}. "
             "Все числа — из реестра фактов EduForecast-SIS; статус каждого факта указан.", ""]
    for c in cards:
        lines += [f"## {c['title']}", "", f"**Наблюдение.** {c['observation']}", ""]
        if c.get("needed_data"):
            lines += [f"**Что нужно собрать.** {c['needed_data']}", ""]
        lines += [f"**Рекомендация.** {c['recommendation']}", "", f"**Риски и ограничения.** {c['risks']}", "",
                  f"**Надёжность:** {c['reliability']}", ""]
        if c["warning"]:
            lines += [f"> {c['warning']}", ""]
        lines += ["Основания:", ""] + [f"- {f['metric']}: {f['status']}; источник `{f['source']}`" for f in c["facts"]]
        lines.append("")
    return "\n".join(lines)


def to_html(cards: list[dict], role_id: str, built_at: str | None) -> str:
    import html

    parts = [f"<h1>Брифинг: {html.escape(ROLES[role_id].name)}</h1>",
             f"<p class='meta'>Реестр фактов от {html.escape(built_at or '—')}. Все числа — из реестра фактов.</p>"]
    for c in cards:
        facts = "".join(f"<li>{html.escape(f['metric'])} — <b>{html.escape(f['status'])}</b>; "
                        f"<code>{html.escape(f['source'])}</code></li>" for f in c["facts"])
        need = f"<p><b>Что нужно собрать.</b> {html.escape(c['needed_data'])}</p>" if c.get("needed_data") else ""
        warn = f"<p class='warn'>{html.escape(c['warning'])}</p>" if c["warning"] else ""
        parts.append(f"<section><h2>{html.escape(c['title'])}</h2><p><b>Наблюдение.</b> "
                     f"{html.escape(c['observation'])}</p>{need}<p><b>Рекомендация.</b> "
                     f"{html.escape(c['recommendation'])}</p><p><b>Риски и ограничения.</b> {html.escape(c['risks'])}"
                     f"</p><p><b>Надёжность:</b> {html.escape(c['reliability'])}</p>{warn}<ul>{facts}</ul></section>")
    style = ("body{font-family:Georgia,'Times New Roman',serif;max-width:760px;margin:32px auto;color:#111;"
             "line-height:1.5}h1{font-size:22px}h2{font-size:17px;border-bottom:1px solid #999;padding-bottom:4px}"
             "section{page-break-inside:avoid;margin-bottom:20px}.warn{border-left:3px solid #92400e;padding-left:8px}"
             ".meta{color:#444;font-size:13px}li{font-size:13px}code{font-size:12px}")
    return (f"<!doctype html><html lang='ru'><head><meta charset='utf-8'><title>Брифинг</title><style>{style}</style>"
            f"</head><body>{''.join(parts)}</body></html>")
