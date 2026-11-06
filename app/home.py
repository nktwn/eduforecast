import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
from components import ui
from components.data_loader import (
    DATA_DIR as OULAD_DIR,
    FACULTY_MAP, get_faculty_data, get_weekly_activity,
    train_risk_model, compute_health_index, get_alerts, get_risk_week, RESULT_RU,
)
from components.charts import activity_line_chart, risk_donut_chart, score_histogram
from components.styles import GLASS_CSS, demo_data_banner, require_data, sidebar_logo


require_data([OULAD_DIR / f for f in ("studentInfo.csv", "studentVle.csv", "studentAssessment.csv", "assessments.csv", "studentRegistration.csv")], "Подготовка данных → Academic (OULAD)")
demo_data_banner()

selected_code = st.session_state.get("selected_faculty", "AAA")
selected_code = sidebar_logo(selected_code, FACULTY_MAP)
faculty_name  = FACULTY_MAP[selected_code]

with st.spinner("Анализ данных факультета..."):
    df_raw              = get_faculty_data(selected_code)
    risk_week           = get_risk_week()
    df_model, quality, _, _ = train_risk_model(selected_code, risk_week)
    weekly              = get_weekly_activity(selected_code)

total       = len(df_raw)
enrolled    = len(df_model)
high_risk   = int((df_model["risk_level"] == "HIGH").sum())
medium_risk = int((df_model["risk_level"] == "MEDIUM").sum())
low_risk    = int((df_model["risk_level"] == "LOW").sum())
high_left   = df_model.loc[df_model["risk_level"] == "HIGH", "is_withdrawn"].mean() * 100 if high_risk else 0
avg_score   = df_raw["avg_score"].mean()
health      = compute_health_index(df_raw)
alerts      = get_alerts(df_raw)

ui.page_header(f"Академический: {faculty_name}", "Обзор условного факультета на демо-данных Open University "
               "(Великобритания).", status="демо")
ui.how_to_read([
    ("Что показывает", "Ключевые показатели факультета, сигналы, активность в LMS по неделям, группы риска и итоги."),
    ("Как читать", f"Группы риска — перцентили на неделе k (выбирается на странице «Студенты»): топ-10%, следующие "
                   f"20%, остальные. {ui.term('AUC')} и качество модели — на странице «Студенты»."),
    ("Результат", "Модель различает будущих ушедших умеренно: группа высокого риска значит «выше среднего»."),
    ("Проверка", "Риск оценён вне обучающей выборки (GroupKFold по студенту) по данным недель ≤ k."),
    ("Оговорки", "Демо-данные OULAD, факультеты условные; на данных AITU модель не проверялась. «Индекс "
                 "здоровья» — составной индекс с весами, заданными вручную."),
])

for a in alerts:
    st.markdown(
        f'<div class="glass-alert" style="border-left-color:{a["color"]};">'
        f'<span><b style="color:{a["color"]};">{a["level"]}</b>'
        f'<span style="color:var(--ef-text-2);"> — {a["msg"]}</span></span>'
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
    st.markdown(
        f'<div class="metric-card accent-amber">'
        f'<div class="metric-value" style="color:var(--ef-warn);">{high_risk:,}</div>'
        f'<div class="metric-label">Высокий риск (топ-10%), неделя {risk_week}</div>'
        f'<div class="metric-delta">из {enrolled:,} ещё учащихся; фактически ушли {high_left:.0f}%</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

with k3:
    sc = "var(--ef-danger)" if avg_score < 40 else "var(--ef-warn)" if avg_score < 60 else "var(--ef-ok)"
    st.markdown(
        f'<div class="metric-card">'
        f'<div class="metric-value" style="color:{sc};">{avg_score:.1f}</div>'
        f'<div class="metric-label">Средний балл</div>'
        f'<div class="metric-delta">Из 100 возможных баллов</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

with k4:
    hc = "var(--ef-danger)" if health < 40 else "var(--ef-warn)" if health < 60 else "var(--ef-primary)" if health < 80 else "var(--ef-ok)"
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
    with st.container(border=True):
        if len(weekly) > 0:
            st.plotly_chart(
                activity_line_chart(weekly),
                width="stretch",
                config={"displayModeBar": False},
            )
        else:
            st.info("Нет данных об активности для этого факультета")

with col_r:
    with st.container(border=True):
        st.plotly_chart(
            risk_donut_chart({"HIGH": high_risk, "MEDIUM": medium_risk, "LOW": low_risk},
                             f"Группы риска на неделе {risk_week} (перцентили)"),
            width="stretch",
            config={"displayModeBar": False},
        )

st.markdown("<br>", unsafe_allow_html=True)

col_a, col_b = st.columns(2)

with col_a:
    with st.container(border=True):
        st.plotly_chart(
            score_histogram(df_raw),
            width="stretch",
            config={"displayModeBar": False},
        )

with col_b:
    with st.container(border=True):
        st.markdown(
            '<div style="font-size:0.8rem; font-weight:600; color:var(--ef-text-2);'
            'margin-bottom:14px;">Итоги по статусам</div>',
            unsafe_allow_html=True,
        )

        result_colors = {
            "Distinction": "var(--ef-ok)", "Pass": "var(--ef-primary)",
            "Fail": "var(--ef-warn)", "Withdrawn": "var(--ef-danger)",
        }

        for result, count in df_raw["final_result"].value_counts().items():
            pct   = count / total * 100
            color = result_colors.get(result, "var(--ef-muted)")
            label = RESULT_RU.get(result, result)
            st.markdown(
                f'<div style="margin-bottom:12px;">'
                f'  <div style="display:flex; justify-content:space-between; margin-bottom:4px;">'
                f'    <span style="color:var(--ef-text-2); font-weight:500; font-size:0.86rem;">'
                f'      {label}</span>'
                f'    <span style="color:var(--ef-text); font-weight:600; font-size:0.86rem;">'
                f'      {count:,} <span style="color:var(--ef-muted); font-weight:400;">({pct:.1f}%)</span></span>'
                f'  </div>'
                f'  <div style="height:4px; border-radius:2px; background:var(--ef-surface-2);">'
                f'    <div style="height:4px; border-radius:2px; width:{pct:.1f}%;'
                f'    background:{color};"></div>'
                f'  </div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        st.markdown('<div style="height:12px;"></div>', unsafe_allow_html=True)
        st.metric("Среднее кликов / студент", f"{df_raw['total_clicks'].mean():,.0f}")
        st.metric("Сдали хотя бы одно задание", f"{(df_raw['assessments_submitted'] > 0).sum():,}")

