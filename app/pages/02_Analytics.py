import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
from components import ui
import pandas as pd
import numpy as np
import requests
from components.data_loader import (
    DATA_DIR as OULAD_DIR,
    FACULTY_MAP, train_risk_model, get_all_faculties_summary, get_retention_data, get_risk_week,
)
from components.risk_model import FEATURE_LABELS
from components.charts import (
    faculty_comparison_chart, withdrawal_comparison_chart,
    retention_forecast_chart, worldbank_chart, shap_bar_chart,
)
from components.styles import GLASS_CSS, demo_data_banner, require_data, sidebar_logo

require_data([OULAD_DIR / f for f in ("studentInfo.csv", "studentVle.csv", "studentAssessment.csv", "assessments.csv", "studentRegistration.csv")], "Подготовка данных → Academic (OULAD)")
demo_data_banner()
st.markdown("""
<style>
.bench-pill {
    background: var(--ef-surface);
    border-radius: 8px;
    border: 1px solid var(--ef-border);
    padding: 16px 14px;
    text-align: center;
}
</style>
""", unsafe_allow_html=True)

selected_code = st.session_state.get("selected_faculty", "AAA")
selected_code = sidebar_logo(selected_code, FACULTY_MAP)
faculty_name  = FACULTY_MAP[selected_code]

ui.page_header("Академический: аналитика", f"{faculty_name} · сравнение факультетов и факторы риска", status="демо")
ui.how_to_read([
    ("Что показывает", "Сравнение условных факультетов, иллюстративные бенчмарки, удержание по неделям, данные "
                       "Всемирного банка по Казахстану, главные факторы риска."),
    ("Как читать", f"Факторы риска — средний |{ui.term('SHAP')}| модели на неделе k."),
    ("Результат", "Описательная аналитика; прогнозом является только модель риска."),
    ("Проверка", "Модель риска — вне обучающей выборки; остальные блоки описательные."),
    ("Оговорки", "Бенчмарки («Мировой топ-100», «Цель AIU» и др.) и цель удержания 75% заданы вручную для "
                 "иллюстрации; удержание — линейная экстраполяция, а не модель."),
])

with st.spinner("Вычисление аналитики..."):
    risk_week = get_risk_week()
    df_model, _, feature_cols, shap_vals = train_risk_model(selected_code, risk_week)
    summary_df = get_all_faculties_summary()

st.markdown('<div class="section-title">Сравнение факультетов</div>', unsafe_allow_html=True)

ca, cb = st.columns(2)
with ca:
    with st.container(border=True):
        st.plotly_chart(faculty_comparison_chart(summary_df),
                        width="stretch", config={"displayModeBar": False})

with cb:
    with st.container(border=True):
        st.plotly_chart(withdrawal_comparison_chart(summary_df),
                        width="stretch", config={"displayModeBar": False})

with st.container(border=True):
    st.markdown(
        '<div style="font-size:0.8rem; font-weight:600; color:var(--ef-text-2);'
        'margin-bottom:14px;">Рейтинг факультетов</div>',
        unsafe_allow_html=True,
    )

    rank = summary_df.sort_values("health_index", ascending=False).reset_index(drop=True)
    rank.index += 1
    rank.index.name = "№"
    disp = rank[["faculty","total_students","withdrawal_rate","avg_score","active_rate","health_index"]].copy()
    disp.columns = ["Факультет","Студентов","% отчислений","Ср. балл","% активных","Индекс здоровья"]

    def _hi(v):
        if v >= 70: return "background:#ecfdf5;color:#065f46;font-weight:600"
        if v >= 50: return "background:#fffbeb;color:#92400e"
        return "background:#fef2f2;color:#991b1b"

    st.dataframe(
        disp.style.map(_hi, subset=["Индекс здоровья"]).format(
            {"% отчислений": "{:.1f}", "Ср. балл": "{:.1f}", "% активных": "{:.1f}", "Индекс здоровья": "{:.1f}"}),
        width="stretch",
    )

st.markdown('<div class="section-title">Бенчмарки (иллюстративные значения)</div>', unsafe_allow_html=True)
st.caption("Значения «Мировой топ-100», «Лучшие в СНГ», «Цель AIU» и «Казахстан» заданы вручную для иллюстрации; "
           "это не официальная статистика.")

curr_wr = summary_df.loc[summary_df["module"] == selected_code, "withdrawal_rate"].values
curr_ret = 100 - float(curr_wr[0]) if len(curr_wr) else 80

BENCHMARKS = [
    ("Текущий факультет", curr_ret, "var(--ef-primary)", "Ваш результат"),
    ("Мировой топ-100",   91,       "var(--ef-text)", "Лучшие университеты мира"),
    ("Лучшие в СНГ",      85,       "var(--ef-text)", "Топ-университеты СНГ"),
    ("Цель AIU",          80,       "var(--ef-text)", "Стратегический целевой показатель"),
    ("Казахстан (ср.)",   74,       "var(--ef-text)", "Среднее по стране"),
]

b_cols = st.columns(len(BENCHMARKS))
for i, (label, val, color, desc) in enumerate(BENCHMARKS):
    is_current = i == 0
    delta = curr_ret - val if not is_current else None
    with b_cols[i]:
        d_html = ""
        if delta is not None:
            dc = "var(--ef-ok)" if delta >= 0 else "var(--ef-danger)"
            d_html = (f'<div style="font-size:0.78rem; font-weight:600; color:{dc}; margin-top:4px;">'
                      f'{"↑" if delta > 0 else "↓" if delta < 0 else "→"} {abs(delta):.1f}%</div>')
        border_style = f"border-top:2px solid {color};" if is_current else ""
        st.markdown(
            f'<div class="bench-pill" style="{border_style}">'
            f'  <div style="font-size:1.6rem; font-weight:700; color:{color};">{val:.1f}%</div>'
            f'  <div style="font-size:0.72rem; font-weight:600; color:var(--ef-text-2); margin-top:4px;">{label}</div>'
            f'  <div style="font-size:0.68rem; color:var(--ef-muted); margin-top:2px;">{desc}</div>'
            f'  {d_html}'
            f'</div>',
            unsafe_allow_html=True,
        )

st.markdown("<br>", unsafe_allow_html=True)

st.markdown('<div class="section-title">Удержание студентов: линейная экстраполяция</div>', unsafe_allow_html=True)
st.caption("Пунктир — продолжение прямой по последним 8 неделям курса, а не прогнозная модель.")

weeks_h, surv_pct, fcst_w, fcst_p = get_retention_data(selected_code)

rf1, rf2 = st.columns([3, 1])
with rf1:
    with st.container(border=True):
        st.plotly_chart(
            retention_forecast_chart(weeks_h, surv_pct, fcst_w, fcst_p),
            width="stretch", config={"displayModeBar": False},
        )

with rf2:
    with st.container(border=True):
        if fcst_p:
            end_v   = fcst_p[-1]
            cur_v   = surv_pct[-1] if surv_pct else 100
            change  = end_v - cur_v
            cc      = "var(--ef-danger)" if change < -5 else "var(--ef-warn)" if change < 0 else "var(--ef-ok)"
            arrow   = "↓" if change < 0 else "→" if change == 0 else "↑"
            status  = "Ниже цели 75%" if end_v < 75 else "Выше цели 75%"
            st_col  = "var(--ef-danger)" if end_v < 75 else "var(--ef-ok)"
            st_bg   = "var(--ef-danger-bg)" if end_v < 75 else "var(--ef-ok-bg)"
            st.markdown(
                f'<div style="padding:16px 0;">'
                f'  <div style="font-size:0.72rem; color:var(--ef-muted);">через 12 недель</div>'
                f'  <div style="font-size:2.4rem; font-weight:700; color:var(--ef-text);'
                f'    line-height:1.2; margin:8px 0;">{end_v:.1f}%</div>'
                f'  <div style="font-size:0.8rem; color:var(--ef-muted);">удержание студентов</div>'
                f'  <div style="font-size:1.1rem; font-weight:600; color:{cc}; margin-top:12px;">'
                f'    {arrow} {abs(change):.1f}%</div>'
                f'  <div style="font-size:0.78rem; color:var(--ef-muted);">изменение от сегодня</div>'
                f'  <div style="font-size:0.82rem; font-weight:600; color:{st_col};'
                f'    margin-top:14px; padding:8px; border-radius:6px;'
                f'    background:{st_bg};">'
                f'    {status}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

st.markdown('<div class="section-title">Образование Казахстана — Всемирный банк</div>', unsafe_allow_html=True)

FALLBACK = {
    "SE.TER.ENRR": pd.DataFrame({"year": [2015,2016,2017,2018,2019,2020,2021],
                                  "value": [49.2,50.1,51.8,53.2,54.9,56.1,57.3]}),
    "SE.XPD.TOTL.GD.ZS": pd.DataFrame({"year": [2015,2016,2017,2018,2019,2020,2021],
                                         "value": [3.1,2.8,2.7,2.9,3.0,3.4,3.6]}),
}

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_wb(indicator: str):
    url = (f"https://api.worldbank.org/v2/country/KZ/indicator/{indicator}"
           f"?format=json&per_page=20&mrv=15")
    try:
        data = requests.get(url, timeout=8).json()
        if len(data) < 2 or not data[1]:
            return None
        rows = [{"year": int(r["date"]), "value": r["value"]}
                for r in data[1] if r["value"] is not None]
        return pd.DataFrame(rows) if rows else None
    except Exception:
        return None

wb1, wb2 = st.columns(2)
INDICATORS = [
    ("SE.TER.ENRR",       "Охват высшим образованием (%) — Казахстан"),
    ("SE.XPD.TOTL.GD.ZS", "Расходы на образование (% ВВП) — Казахстан"),
]
for col, (ind, lbl) in zip([wb1, wb2], INDICATORS):
    df_wb = fetch_wb(ind)
    if df_wb is None or df_wb.empty:
        df_wb  = FALLBACK[ind]
        lbl   += " (справочно)"
    with col:
        with st.container(border=True):
            st.plotly_chart(worldbank_chart(df_wb, lbl),
                            width="stretch", config={"displayModeBar": False})

st.markdown(f'<div class="section-title">Факторы риска — SHAP анализ (неделя {risk_week})</div>',
            unsafe_allow_html=True)

sh1, sh2 = st.columns([3, 1])
mean_shap = np.abs(shap_vals).mean(axis=0)

with sh1:
    with st.container(border=True):
        st.plotly_chart(shap_bar_chart(feature_cols, mean_shap),
                        width="stretch", config={"displayModeBar": False})

with sh2:
    with st.container(border=True):
        st.markdown(
            '<div style="font-size:0.8rem; font-weight:600; color:var(--ef-text-2);'
            'margin-bottom:12px;">Топ факторы</div>',
            unsafe_allow_html=True,
        )
        feat_labels = FEATURE_LABELS
        for rank_i, idx in enumerate(np.argsort(mean_shap)[::-1][:6], 1):
            val  = float(mean_shap[idx])
            lbl  = feat_labels.get(feature_cols[idx], feature_cols[idx])
            bar  = min(100, val * 500)
            st.markdown(
                f'<div style="margin-bottom:10px;">'
                f'  <div style="display:flex; justify-content:space-between; font-size:0.8rem;">'
                f'    <span style="color:var(--ef-text-2); font-weight:500;">#{rank_i} {lbl}</span>'
                f'    <span style="color:var(--ef-text); font-weight:600;">{val:.3f}</span>'
                f'  </div>'
                f'  <div style="height:4px; background:var(--ef-surface-2);'
                f'    border-radius:2px; margin-top:4px;">'
                f'    <div style="height:4px; border-radius:2px; width:{bar:.0f}%;'
                f'    background:var(--ef-primary);"></div>'
                f'  </div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        st.markdown(
            '<div style="font-size:0.7rem; color:var(--ef-muted); margin-top:12px; line-height:1.6;">'
            'Чем выше |SHAP|, тем сильнее фактор влияет на предсказание риска отчисления. '
            f'Модель видит только данные до конца недели {risk_week}; SHAP посчитан для ещё учащихся '
            'моделью, которая их не видела.</div>',
            unsafe_allow_html=True,
        )
