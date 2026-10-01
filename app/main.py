import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
from components.data_loader import (
    FACULTY_MAP, get_faculty_data, get_weekly_activity,
    train_risk_model, compute_health_index, get_alerts, RESULT_RU,
)
from components.charts import activity_line_chart, risk_donut_chart, score_histogram
from components.styles import GLASS_CSS, sidebar_logo

st.set_page_config(
    page_title="EduForecast-SIS | AIU",
    page_icon="А",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(GLASS_CSS, unsafe_allow_html=True)

selected_code = st.session_state.get("selected_faculty", "AAA")
selected_code = sidebar_logo(selected_code, FACULTY_MAP)
faculty_name  = FACULTY_MAP[selected_code]

with st.spinner("Анализ данных факультета..."):
    df_raw              = get_faculty_data(selected_code)
    df_model, _, _, _   = train_risk_model(selected_code)
    weekly              = get_weekly_activity(selected_code)

total       = len(df_model)
high_risk   = int((df_model["risk_level"] == "HIGH").sum())
medium_risk = int((df_model["risk_level"] == "MEDIUM").sum())
low_risk    = int((df_model["risk_level"] == "LOW").sum())
high_pct    = high_risk / total * 100 if total else 0
avg_score   = df_raw["avg_score"].mean()
health      = compute_health_index(df_raw)
alerts      = get_alerts(df_raw)

st.markdown(
    f"""
    <div style="font-size:0.78rem; color:#6b7280; margin-bottom:2px;">
        Стратегический дашборд
    </div>
    <h1 style="margin:0 0 4px 0; font-size:1.7rem;">{faculty_name}</h1>
    <p style="color:#9ca3af; margin:0 0 20px 0; font-size:0.85rem;">
        Astana IT University · EduForecast-SIS
    </p>
    """,
    unsafe_allow_html=True,
)

for a in alerts:
    st.markdown(
        f'<div class="glass-alert" style="border-left-color:{a["color"]};">'
        f'<span><b style="color:{a["color"]};">{a["level"]}</b>'
        f'<span style="color:#374151;"> — {a["msg"]}</span></span>'
        f'</div>',
        unsafe_allow_html=True,
    )

st.markdown('<div class="section-title">Ключевые показатели</div>', unsafe_allow_html=True)

k1, k2, k3, k4 = st.columns(4)

with k1:
    st.markdown(
        f'<div class="metric-card">'
        f'<div class="metric-value">{total:,}</div>'
        f'<div class="metric-label">Студентов</div>'
        f'<div class="metric-delta">Все презентации модуля</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

with k2:
    accent = "accent-red" if high_pct > 30 else "accent-amber" if high_pct > 15 else "accent-green"
    val_color = "#dc2626" if high_pct > 30 else "#d97706" if high_pct > 15 else "#059669"
    st.markdown(
        f'<div class="metric-card {accent}">'
        f'<div class="metric-value" style="color:{val_color};">{high_pct:.1f}%</div>'
        f'<div class="metric-label">Высокий риск</div>'
        f'<div class="metric-delta">{high_risk} студентов требуют внимания</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

with k3:
    sc = "#dc2626" if avg_score < 40 else "#d97706" if avg_score < 60 else "#059669"
    st.markdown(
        f'<div class="metric-card">'
        f'<div class="metric-value" style="color:{sc};">{avg_score:.1f}</div>'
        f'<div class="metric-label">Средний балл</div>'
        f'<div class="metric-delta">Из 100 возможных баллов</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

with k4:
    hc = "#dc2626" if health < 40 else "#d97706" if health < 60 else "#2563eb" if health < 80 else "#059669"
    hl = "Критично" if health < 40 else "Внимание" if health < 60 else "Хорошо" if health < 80 else "Отлично"
    st.markdown(
        f'<div class="metric-card">'
        f'<div class="metric-value" style="color:{hc};">{health:.0f}</div>'
        f'<div class="metric-label">Индекс здоровья</div>'
        f'<div class="metric-delta">из 100 — <b style="color:{hc};">{hl}</b></div>'
        f'</div>',
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)

col_l, col_r = st.columns([2, 1])

with col_l:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    if len(weekly) > 0:
        st.plotly_chart(
            activity_line_chart(weekly),
            use_container_width=True,
            config={"displayModeBar": False},
        )
    else:
        st.info("Нет данных об активности для этого факультета")
    st.markdown("</div>", unsafe_allow_html=True)

with col_r:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.plotly_chart(
        risk_donut_chart({"HIGH": high_risk, "MEDIUM": medium_risk, "LOW": low_risk}),
        use_container_width=True,
        config={"displayModeBar": False},
    )
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

col_a, col_b = st.columns(2)

with col_a:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.plotly_chart(
        score_histogram(df_raw),
        use_container_width=True,
        config={"displayModeBar": False},
    )
    st.markdown("</div>", unsafe_allow_html=True)

with col_b:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown(
        '<div style="font-size:0.8rem; font-weight:600; color:#374151;'
        'margin-bottom:14px;">Итоги по статусам</div>',
        unsafe_allow_html=True,
    )

    result_colors = {
        "Distinction": "#059669", "Pass": "#2563eb",
        "Fail": "#d97706", "Withdrawn": "#dc2626",
    }

    for result, count in df_raw["final_result"].value_counts().items():
        pct   = count / total * 100
        color = result_colors.get(result, "#6b7280")
        label = RESULT_RU.get(result, result)
        st.markdown(
            f'<div style="margin-bottom:12px;">'
            f'  <div style="display:flex; justify-content:space-between; margin-bottom:4px;">'
            f'    <span style="color:#374151; font-weight:500; font-size:0.86rem;">'
            f'      {label}</span>'
            f'    <span style="color:#0f172a; font-weight:600; font-size:0.86rem;">'
            f'      {count:,} <span style="color:#9ca3af; font-weight:400;">({pct:.1f}%)</span></span>'
            f'  </div>'
            f'  <div style="height:4px; border-radius:2px; background:#eef0f3;">'
            f'    <div style="height:4px; border-radius:2px; width:{pct:.1f}%;'
            f'    background:{color};"></div>'
            f'  </div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div style="height:12px;"></div>', unsafe_allow_html=True)
    st.metric("Среднее кликов / студент", f"{df_raw['total_clicks'].mean():,.0f}")
    st.metric("Сдали хотя бы одно задание", f"{(df_raw['assessments_submitted'] > 0).sum():,}")

    st.markdown("</div>", unsafe_allow_html=True)
