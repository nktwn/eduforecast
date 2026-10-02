import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st

from components.data_loader import FACULTY_MAP
from components.research_data_loader import INSTITUTION_NAME, TRAINING_WINDOW, get_forecast_comparison
from components.research_charts import forecast_comparison_chart
from components.styles import GLASS_CSS, sidebar_logo

st.set_page_config(
    page_title="Научная продуктивность | EduForecast-SIS",
    page_icon="Н",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(GLASS_CSS, unsafe_allow_html=True)

selected_code = st.session_state.get("selected_faculty", "AAA")
sidebar_logo(selected_code, FACULTY_MAP)

st.markdown(
    f'<h1 style="margin:0 0 4px 0; font-size:1.7rem;">Научная продуктивность</h1>'
    f'<p style="color:#9ca3af; margin:0 0 22px 0; font-size:0.85rem;">'
    f'{INSTITUTION_NAME} · данные OpenAlex · весь вуз целиком, без разбивки по факультетам</p>',
    unsafe_allow_html=True,
)

st.warning(
    "**Proof-of-concept, не высокоточный прогноз.** Модель обучена всего на "
    f"{TRAINING_WINDOW[1] - TRAINING_WINDOW[0] + 1} годовых точках "
    f"({TRAINING_WINDOW[0]}–{TRAINING_WINDOW[1]}; 2019 исключён — всего 1 публикация, "
    "дорегистрационный период вуза). При таком малом N доверительные интервалы "
    "прогноза широкие, а бэктест ниже — это проверка на одном отложенном годе, "
    "**не** кросс-валидация.",
    icon="⚠️",
)

with st.spinner("Загрузка данных и построение прогноза..."):
    comparison = get_forecast_comparison()

st.markdown('<div class="section-title">Факт и прогноз (linear vs logistic)</div>', unsafe_allow_html=True)

st.markdown('<div class="glass-card">', unsafe_allow_html=True)
st.plotly_chart(
    forecast_comparison_chart(
        comparison.history,
        comparison.linear_forecast,
        comparison.logistic_forecast,
        comparison.logistic_cap,
    ),
    use_container_width=True, config={"displayModeBar": False},
)
st.markdown(
    '<div style="font-size:0.72rem; color:#9ca3af; margin-top:8px; line-height:1.6;">'
    'Потолок логистической модели — экспертная оценка (текущий пик × 2), а не величина, '
    'выведенная из данных (см. src/research/config.py).</div>',
    unsafe_allow_html=True,
)
st.markdown("</div>", unsafe_allow_html=True)

st.markdown('<div class="section-title">Бэктест: leave-last-year-out (sanity check)</div>', unsafe_allow_html=True)

bt = comparison.backtest
st.caption(bt.note)

bc1, bc2, bc3 = st.columns(3)
with bc1:
    st.markdown('<div class="glass-card" style="text-align:center;">', unsafe_allow_html=True)
    st.markdown(
        f'<div style="font-size:0.72rem; color:#9ca3af;">Факт {bt.backtest_year}</div>'
        f'<div style="font-size:2rem; font-weight:700; color:#0f172a;">{bt.actual:.0f}</div>',
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

for col, growth, label in ((bc2, "linear", "Linear"), (bc3, "logistic", "Logistic")):
    pred = bt.predictions[growth]
    with col:
        st.markdown('<div class="glass-card" style="text-align:center;">', unsafe_allow_html=True)
        st.markdown(
            f'<div style="font-size:0.72rem; color:#9ca3af;">Прогноз ({label}) на {bt.backtest_year}</div>'
            f'<div style="font-size:2rem; font-weight:700; color:#0f172a;">{pred["predicted"]:.0f}</div>'
            f'<div style="font-size:0.78rem; color:#6b7280; margin-top:4px;">'
            f'[{pred["lower"]:.0f}, {pred["upper"]:.0f}]</div>'
            f'<div style="font-size:0.85rem; font-weight:600; color:#dc2626; margin-top:8px;">'
            f'Ошибка: {pred["abs_error"]:.0f} ({pred["pct_error"]:.1f}%)</div>',
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)
