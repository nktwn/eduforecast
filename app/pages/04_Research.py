import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
from components import research_stage3, ui

from components.research_data_loader import INSTITUTION_NAME, TRAINING_WINDOW, get_forecast_comparison
from components.research_charts import forecast_comparison_chart
from components.styles import GLASS_CSS, require_data, sidebar_brand
from src.research.config import OPENALEX_INSTITUTION_ID, RAW_DIR as RESEARCH_RAW_DIR


sidebar_brand("Модуль Research", "Данные: OpenAlex, панель 50 вузов<br>Модели: LightGBM, Ridge; иллюстрация Prophet")

ui.page_header("Научный", f"{INSTITUTION_NAME} и панель 50 вузов · данные OpenAlex · весь вуз, без разбивки "
               "по факультетам")
ui.how_to_read([
    ("Что показывает", "Проверку прогноза на панели 50 вузов, прогноз AITU на 2026 и положение AITU среди вузов "
                       "панели; ниже — прежняя иллюстрация Prophet."),
    ("Как читать", f"Выигрыш — насколько ошибка модели меньше ошибки {ui.term('naive')}. C1 — лучше naive, "
                   "C2 — лучше среднего роста панели и возрастной группы."),
    ("Результат", "Модели лучше naive для счётчиков (публикации, авторы, цитирования, международные связи), "
                  "но не для долей; лучше среднего роста — ни для одного показателя."),
    ("Проверка", "Критерии зафиксированы до запуска; rolling origin и leave-one-university-out 2019–2025; "
                 "STAGE3_REPORT.md."),
    ("Оговорки", "OpenAlex учитывает не все публикации и меняет данные задним числом; процентили — описательный "
                 "бенчмарк, не причинность."),
])

research_stage3.render()

st.markdown('<div class="section-title">Иллюстрация: Prophet по ряду AITU</div>', unsafe_allow_html=True)
ui.status_badge("исследовательское")
st.caption("Ряд для этой иллюстрации — сохранённая ранее копия годовых счётчиков OpenAlex без исключения отозванных "
           "работ и paratext. Поэтому число публикаций за год здесь может отличаться от панели выше "
           "(выгрузка 2026-10-19, правила этапа 3).")
require_data([RESEARCH_RAW_DIR / f"yearly_work_counts_{OPENALEX_INSTITUTION_ID}.json"], "Подготовка данных → Research (OpenAlex)")

with st.spinner("Загрузка данных и построение прогноза..."):
    comparison = get_forecast_comparison()

partial_note = ""
if not comparison.partial.empty:
    partial_list = ", ".join(str(y) for y in comparison.partial["year"])
    partial_note = (
        f" Год {partial_list} неполный (данные на текущую дату): показан на графике "
        "отдельной точкой и не используется ни в обучении, ни в оценке."
    )

ui.caveat(

    " Модель обучена всего на "
    f"{TRAINING_WINDOW[1] - TRAINING_WINDOW[0] + 1} полных годовых точках "
    f"({TRAINING_WINDOW[0]}–{TRAINING_WINDOW[1]}; 2019 исключён — всего 1 публикация, "
    "дорегистрационный период вуза). При таком малом N доверительные интервалы "
    "прогноза широкие, а бэктест ниже — это проверка на одном отложенном годе, "
    f"<b>не</b> кросс-валидация.{partial_note}",
    title="Proof-of-concept, не высокоточный прогноз",
)

st.markdown('<div class="section-title">Факт и прогноз (linear vs logistic)</div>', unsafe_allow_html=True)

with st.container(border=True):
    st.plotly_chart(
        forecast_comparison_chart(
            comparison.history,
            comparison.linear_forecast,
            comparison.logistic_forecast,
            comparison.logistic_cap,
            comparison.partial,
        ),
        width="stretch", config={"displayModeBar": False},
    )
    st.markdown(
        '<div style="font-size:0.72rem; color:var(--ef-muted); margin-top:8px; line-height:1.6;">'
        'Потолок логистической модели — экспертная оценка (текущий пик × 2), а не величина, '
        'выведенная из данных (см. src/research/config.py).</div>',
        unsafe_allow_html=True,
    )

st.markdown('<div class="section-title">Бэктест: leave-last-year-out (sanity check)</div>', unsafe_allow_html=True)

bt = comparison.backtest
st.caption(bt.note)

bc1, bc2, bc3 = st.columns(3)
with bc1:
    with st.container(border=True):
        st.markdown(
            f'<div style="font-size:0.72rem; color:var(--ef-muted);">Факт {bt.backtest_year}</div>'
            f'<div style="font-size:2rem; font-weight:700; color:var(--ef-text);">{bt.actual:.0f}</div>',
            unsafe_allow_html=True,
        )

for col, growth, label in ((bc2, "linear", "Linear"), (bc3, "logistic", "Logistic")):
    pred = bt.predictions[growth]
    with col:
        with st.container(border=True):
            st.markdown(
                f'<div style="font-size:0.72rem; color:var(--ef-muted);">Прогноз ({label}) на {bt.backtest_year}</div>'
                f'<div style="font-size:2rem; font-weight:700; color:var(--ef-text);">{pred["predicted"]:.0f}</div>'
                f'<div style="font-size:0.78rem; color:var(--ef-muted); margin-top:4px;">'
                f'[{pred["lower"]:.0f}, {pred["upper"]:.0f}]</div>'
                f'<div style="font-size:0.85rem; font-weight:600; color:var(--ef-danger); margin-top:8px;">'
                f'Ошибка: {pred["abs_error"]:.0f} ({pred["pct_error"]:.1f}%)</div>',
                unsafe_allow_html=True,
            )
