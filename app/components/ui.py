"""UI components: header, KPI card with status, status badge, caveat, advice card, evidence panel,
empty state, loading, data-mode banner, glossary tooltips. All colors come from theme.css() variables."""
from __future__ import annotations

import html
from contextlib import contextmanager

import streamlit as st

from components import theme

GLOSSARY = {
    "AUC": "Насколько хорошо модель отличает ушедших от оставшихся: 0,5 — случайное угадывание, 1 — идеально.",
    "naive": "Простейший ориентир «как в прошлом году». Модель полезна, только если стабильно лучше него.",
    "SHAP": "Разложение прогноза на вклады признаков: какой фактор поднял или опустил оценку и насколько.",
    "k": "Неделя прогноза: модель видит только данные до конца недели k семестра.",
    "Brier": "Средний квадрат ошибки вероятности: чем меньше, тем точнее вероятности.",
    "MAE": "Средняя абсолютная ошибка прогноза.",
    "precision": "Какая доля студентов из группы высокого риска действительно ушла.",
    "охват": "Какая доля всех ушедших попала в группу высокого риска.",
    "перцентиль": "P50 — медиана: половина вузов-аналогов ниже, половина выше; P10 и P90 — края типичного диапазона.",
}
STATUS_HELP = {
    "проверено": "Число получено зафиксированной заранее или проверенной аудитом процедурой.",
    "исследовательское": "Получено после основного прогона, на неверифицированных данных или как иллюстрация.",
    "демо": "Демонстрация на данных, которые не являются данными вуза (например, OULAD) или на ручных значениях.",
    "нет данных": "Данных нет: показатель не рассчитан.",
    "концепция": "Направление описано, но не реализовано.",
}


def inject_css() -> None:
    st.markdown(theme.css(), unsafe_allow_html=True)


def esc(x) -> str:
    return html.escape(str(x))


def term(word: str, label: str | None = None) -> str:
    tip = GLOSSARY.get(word, "")
    return f'<span class="ef-term" title="{esc(tip)}">{esc(label or word)}</span>' if tip else esc(label or word)


def badge_html(status: str) -> str:
    p = theme.palette()
    fg, bg = theme.STATUS_STYLE.get(status, ("muted", "surface_2"))
    return (f'<span class="ef-badge" title="{esc(STATUS_HELP.get(status, ""))}" '
            f'style="color:{p[fg]};background:{p[bg]};border:1px solid {p[fg]}33">{esc(status)}</span>')


def status_badge(status: str) -> None:
    st.markdown(badge_html(status), unsafe_allow_html=True)


def page_header(title: str, subtitle: str = "", status: str | None = None) -> None:
    b = f" {badge_html(status)}" if status else ""
    st.markdown(f'<div class="ef-header"><h1>{esc(title)}{b}</h1>'
                f'{f"<div class=ef-sub>{esc(subtitle)}</div>" if subtitle else ""}</div>', unsafe_allow_html=True)


def kpi_card(label: str, value: str, status: str | None = None, hint: str = "", help_text: str = "") -> None:
    b = badge_html(status) if status else ""
    tip = f' title="{esc(help_text)}"' if help_text else ""
    st.markdown(f'<div class="ef-card"{tip}><div class="ef-kpi-label">{esc(label)} {b}</div>'
                f'<div class="ef-kpi-value">{esc(value)}</div><div class="ef-kpi-hint">{hint}</div></div>',
                unsafe_allow_html=True)


def caveat(text: str, title: str = "Оговорка") -> None:
    st.markdown(f'<div class="ef-caveat"><b>{esc(title)}.</b> {text}</div>', unsafe_allow_html=True)


def data_mode_banner(text: str) -> None:
    st.markdown(f'<div class="ef-banner">{text}</div>', unsafe_allow_html=True)


def empty_state(title: str, text: str = "") -> None:
    st.markdown(f'<div class="ef-empty"><b>{esc(title)}</b>{esc(text)}</div>', unsafe_allow_html=True)


@contextmanager
def loading(text: str = "Загрузка…"):
    with st.spinner(text):
        yield


def advice_card(card: dict) -> None:
    """Card from the advisor (briefing or answer): observation -> basis -> recommendation -> risks -> reliability."""
    need = (f'<p><span class="ef-k">Что нужно собрать.</span> {esc(card["needed_data"])}</p>'
            if card.get("needed_data") else "")
    title = f"<h4>{esc(card['title'])}</h4>" if card.get("title") else ""
    with st.container(border=True):
        st.markdown(
            f'<div class="ef-advice">{title}'
            f'<p><span class="ef-k">Наблюдение.</span> {esc(card["observation"])}</p>{need}'
            f'<p><span class="ef-k">Рекомендация.</span> {esc(card["recommendation"])}</p>'
            f'<p><span class="ef-k">Риски и ограничения.</span> {esc(card["risks"])}</p>'
            f'<p><span class="ef-k">Надёжность:</span> {badge_html(card["reliability"])}</p></div>',
            unsafe_allow_html=True)
        if card.get("warning"):
            st.markdown(f'<div class="ef-caveat">{esc(card["warning"])}</div>', unsafe_allow_html=True)
        if card.get("facts"):
            with st.expander(f"Основания ({len(card['facts'])})"):
                evidence_panel(card["facts"])


def evidence_panel(facts: list[dict]) -> None:
    from src.advisor.facts.fmt import format_value

    for f in facts:
        st.markdown(f'{badge_html(f["status"])} **{esc(f["metric"])}** — {esc(format_value(f["value"], f["unit"]))}'
                    f' <span class="ef-muted">· {esc(f["period"])}</span><br>'
                    f'<span class="ef-muted" style="font-size:0.8rem">{esc(f["caveat"])} Источник: '
                    f'<code>{esc(f["source"])}</code></span>', unsafe_allow_html=True)


def light(status: str) -> str:
    """Traffic light for module readiness."""
    p = theme.palette()
    color = {"проверено": p["ok"], "исследовательское": p["research"], "демо": p["demo"],
             "нет данных": p["danger"], "концепция": p["nodata"]}.get(status, p["muted"])
    return f'<span class="ef-light" style="background:{color}"></span>'


def how_to_read(items: list[tuple[str, str]]) -> None:
    """The common page structure: what it shows / how to read / result / check / caveats."""
    with st.expander("Как читать эту страницу", expanded=False):
        for k, v in items:
            st.markdown(f"**{k}.** {v}", unsafe_allow_html=True)
