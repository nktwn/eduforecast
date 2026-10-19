"""Research stage 3 block: panel of 50 universities, criteria C1/C2, AITU forecast and percentiles.

Reads only the fact registry snapshot (src/advisor/facts/snapshot.json), so it works in a fresh clone.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from components import ui  # noqa: E402
from src.advisor.facts.builders import STAGE3_TARGETS  # noqa: E402
from src.advisor.facts.registry import registry  # noqa: E402


def _val(reg, fid):
    f = reg.get(fid)
    return (reg.display(fid), f["status"]) if f else ("нет данных", "нет данных")


def render() -> None:
    reg = registry()
    st.markdown('<div class="section-title">Панель 50 вузов: проверка прогноза (этап 3)</div>',
                unsafe_allow_html=True)
    st.caption("Казахстан 35, Турция 7, Россия 4, Польша, Узбекистан, Азербайджан, Южная Корея по 1; OpenAlex на "
               "2026-10-19. Прогноз на год вперёд, проверка 2019–2025. Выигрыш — насколько ошибка модели меньше "
               "ошибки naive. C1 — лучше naive в обеих схемах, C2 — лучше среднего роста панели и возрастной группы. "
               "Покрытие — доля фактов внутри 80% интервала. Критерии и основная модель зафиксированы до запуска "
               "(STAGE3_REPORT.md).")
    rows = []
    for t, label in STAGE3_TARGETS.items():
        rows.append({
            "Показатель": label,
            "Выигрыш, rolling": _val(reg, f"research.stage3.{t}.c1_gain_rolling")[0],
            "Выигрыш, LOUO": _val(reg, f"research.stage3.{t}.c1_gain_louo")[0],
            "C1": _val(reg, f"research.stage3.{t}.c1_passed")[0],
            "C2": _val(reg, f"research.stage3.{t}.c2_passed")[0],
            "Покрытие 80%": _val(reg, f"research.stage3.{t}.conformal_coverage")[0],
        })
    with st.container(border=True):
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        st.markdown(f'Статус: {ui.badge_html("проверено")} — результат по заранее зафиксированному критерию, '
                    'воспроизведён повторным запуском.', unsafe_allow_html=True)
    ui.caveat("Модели лучше naive («без изменения») для счётчиков, включая международные, но не для долей. "
              "Ни для одного показателя модель не обходит простой средний рост панели и возрастной группы "
              "на 10% (критерий C2): основной выигрыш даёт сам факт, что вузы в среднем растут.",
              title="Как понимать")

    st.markdown('<div class="section-title">AITU: прогноз на 2026</div>', unsafe_allow_html=True)
    rows = []
    for t, label in STAGE3_TARGETS.items():
        lo, hi = reg.get(f"research.aitu.stage3.{t}.lower80_2026"), reg.get(f"research.aitu.stage3.{t}.upper80_2026")
        fc = _val(reg, f"research.aitu.stage3.{t}.forecast_2026")[0]
        fc = "не строится (C1 не пройден)" if fc.startswith("прогноз не строится") else fc
        rows.append({"Показатель": label, "Прогноз 2026": fc,
                     "Интервал 80%": f"{reg.display(lo['id'])} – {reg.display(hi['id'])}" if lo and hi else "—"})
    with st.container(border=True):
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        st.markdown(f'Статус: {ui.badge_html("исследовательское")} — AITU не входит в обучение (короткий ряд); '
                    'прогноз только для показателей, прошедших C1. C2 не пройден: прогноз не доказанно точнее '
                    'среднего роста. Интервал цитирований неинформативен из-за быстрого старта AITU в 2020–2022.',
                    unsafe_allow_html=True)

    st.markdown('<div class="section-title">AITU среди 50 вузов панели, 2025</div>', unsafe_allow_html=True)
    cols = st.columns(4)
    for col, (m, label) in zip(cols, (("works_count", "Публикации"), ("citations_per_author", "Цитирования на автора"),
                                      ("intl_collab_share", "Доля междунар. соавторств"),
                                      ("n_partner_countries", "Страны-партнёры"))):
        f = reg.get(f"research.aitu.stage3.percentile.{m}")
        value = "нет данных" if f is None or f["value"] is None else f"{round(f['value'] * 100)}-й процентиль"
        with col:
            ui.kpi_card(label, value, status=f["status"] if f else "нет данных")
    ui.caveat("Описательный бенчмарк, не причинность: показывает, где AITU среди вузов панели, но не почему и не "
              "что изменится от каких-либо действий.", title="Процентили")
