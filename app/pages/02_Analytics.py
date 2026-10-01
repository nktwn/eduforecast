import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd
import numpy as np
import requests
from components.data_loader import (
    FACULTY_MAP, train_risk_model, get_all_faculties_summary, get_retention_data,
)
from components.charts import (
    faculty_comparison_chart, withdrawal_comparison_chart,
    retention_forecast_chart, worldbank_chart, shap_bar_chart,
)
from components.styles import GLASS_CSS, sidebar_logo

st.set_page_config(
    page_title="Аналитика | EduForecast-SIS",
    page_icon="А",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(GLASS_CSS, unsafe_allow_html=True)
st.markdown("""
<style>
.bench-pill {
    background: #ffffff;
    border-radius: 8px;
    border: 1px solid #e3e6eb;
    padding: 16px 14px;
    text-align: center;
}
</style>
""", unsafe_allow_html=True)

selected_code = st.session_state.get("selected_faculty", "AAA")
selected_code = sidebar_logo(selected_code, FACULTY_MAP)
faculty_name  = FACULTY_MAP[selected_code]

st.markdown(
    f'<h1 style="margin:0 0 4px 0; font-size:1.7rem;">Аналитика</h1>'
    f'<p style="color:#9ca3af; margin:0 0 22px 0; font-size:0.85rem;">{faculty_name}</p>',
    unsafe_allow_html=True,
)

with st.spinner("Вычисление аналитики..."):
    df_model, _, feature_cols, shap_vals = train_risk_model(selected_code)
    summary_df = get_all_faculties_summary()

st.markdown('<div class="section-title">Сравнение факультетов</div>', unsafe_allow_html=True)

ca, cb = st.columns(2)
with ca:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.plotly_chart(faculty_comparison_chart(summary_df),
                    use_container_width=True, config={"displayModeBar": False})
    st.markdown("</div>", unsafe_allow_html=True)

with cb:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.plotly_chart(withdrawal_comparison_chart(summary_df),
                    use_container_width=True, config={"displayModeBar": False})
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown('<div class="glass-card">', unsafe_allow_html=True)
st.markdown(
    '<div style="font-size:0.8rem; font-weight:600; color:#374151;'
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
    disp.style.map(_hi, subset=["Индекс здоровья"]),
    use_container_width=True,
)
st.markdown("</div>", unsafe_allow_html=True)

st.markdown('<div class="section-title">Международные бенчмарки</div>', unsafe_allow_html=True)

curr_wr = summary_df.loc[summary_df["module"] == selected_code, "withdrawal_rate"].values
curr_ret = 100 - float(curr_wr[0]) if len(curr_wr) else 80

BENCHMARKS = [
    ("Текущий факультет", curr_ret, "#2563eb", "Ваш результат"),
    ("Мировой топ-100",   91,       "#0f172a", "Лучшие университеты мира"),
    ("Лучшие в СНГ",      85,       "#0f172a", "Топ-университеты СНГ"),
    ("Цель AIU",          80,       "#0f172a", "Стратегический целевой показатель"),
    ("Казахстан (ср.)",   74,       "#0f172a", "Среднее по стране"),
]

b_cols = st.columns(len(BENCHMARKS))
for i, (label, val, color, desc) in enumerate(BENCHMARKS):
    is_current = i == 0
    delta = curr_ret - val if not is_current else None
    with b_cols[i]:
        d_html = ""
        if delta is not None:
            dc = "#059669" if delta >= 0 else "#dc2626"
            d_html = (f'<div style="font-size:0.78rem; font-weight:600; color:{dc}; margin-top:4px;">'
                      f'{"↑" if delta > 0 else "↓" if delta < 0 else "→"} {abs(delta):.1f}%</div>')
        border_style = f"border-top:2px solid {color};" if is_current else ""
        st.markdown(
            f'<div class="bench-pill" style="{border_style}">'
            f'  <div style="font-size:1.6rem; font-weight:700; color:{color};">{val:.1f}%</div>'
            f'  <div style="font-size:0.72rem; font-weight:600; color:#374151; margin-top:4px;">{label}</div>'
            f'  <div style="font-size:0.68rem; color:#9ca3af; margin-top:2px;">{desc}</div>'
            f'  {d_html}'
            f'</div>',
            unsafe_allow_html=True,
        )

st.markdown("<br>", unsafe_allow_html=True)

st.markdown('<div class="section-title">Прогноз удержания студентов</div>', unsafe_allow_html=True)

weeks_h, surv_pct, fcst_w, fcst_p = get_retention_data(selected_code)

rf1, rf2 = st.columns([3, 1])
with rf1:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.plotly_chart(
        retention_forecast_chart(weeks_h, surv_pct, fcst_w, fcst_p),
        use_container_width=True, config={"displayModeBar": False},
    )
    st.markdown("</div>", unsafe_allow_html=True)

with rf2:
    st.markdown('<div class="glass-card" style="text-align:center;">', unsafe_allow_html=True)
    if fcst_p:
        end_v   = fcst_p[-1]
        cur_v   = surv_pct[-1] if surv_pct else 100
        change  = end_v - cur_v
        cc      = "#dc2626" if change < -5 else "#d97706" if change < 0 else "#059669"
        arrow   = "↓" if change < 0 else "→" if change == 0 else "↑"
        status  = "Ниже цели 75%" if end_v < 75 else "Выше цели 75%"
        st_col  = "#dc2626" if end_v < 75 else "#059669"
        st_bg   = "#fef2f2" if end_v < 75 else "#ecfdf5"
        st.markdown(
            f'<div style="padding:16px 0;">'
            f'  <div style="font-size:0.72rem; color:#9ca3af;">через 12 недель</div>'
            f'  <div style="font-size:2.4rem; font-weight:700; color:#0f172a;'
            f'    line-height:1.2; margin:8px 0;">{end_v:.1f}%</div>'
            f'  <div style="font-size:0.8rem; color:#6b7280;">удержание студентов</div>'
            f'  <div style="font-size:1.1rem; font-weight:600; color:{cc}; margin-top:12px;">'
            f'    {arrow} {abs(change):.1f}%</div>'
            f'  <div style="font-size:0.78rem; color:#9ca3af;">изменение от сегодня</div>'
            f'  <div style="font-size:0.82rem; font-weight:600; color:{st_col};'
            f'    margin-top:14px; padding:8px; border-radius:6px;'
            f'    background:{st_bg};">'
            f'    {status}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)

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
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.plotly_chart(worldbank_chart(df_wb, lbl),
                        use_container_width=True, config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)

st.markdown('<div class="section-title">Факторы риска — SHAP анализ</div>', unsafe_allow_html=True)

sh1, sh2 = st.columns([3, 1])
mean_shap = np.abs(shap_vals).mean(axis=0)

with sh1:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.plotly_chart(shap_bar_chart(feature_cols, mean_shap),
                    use_container_width=True, config={"displayModeBar": False})
    st.markdown("</div>", unsafe_allow_html=True)

with sh2:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown(
        '<div style="font-size:0.8rem; font-weight:600; color:#374151;'
        'margin-bottom:12px;">Топ факторы</div>',
        unsafe_allow_html=True,
    )
    feat_labels = {
        "total_clicks": "Активность в LMS",
        "active_days":  "Активные дни",
        "assessments_submitted": "Задания",
        "avg_score":    "Средний балл",
        "min_score":    "Мин. балл",
        "num_of_prev_attempts": "Повт. попытки",
        "studied_credits": "Нагрузка",
        "unregistered": "Регистрация",
        "edu_enc":      "Образование",
        "imd_enc":      "Соц. фактор",
        "age_enc":      "Возраст",
    }
    for rank_i, idx in enumerate(np.argsort(mean_shap)[::-1][:6], 1):
        val  = float(mean_shap[idx])
        lbl  = feat_labels.get(feature_cols[idx], feature_cols[idx])
        bar  = min(100, val * 500)
        st.markdown(
            f'<div style="margin-bottom:10px;">'
            f'  <div style="display:flex; justify-content:space-between; font-size:0.8rem;">'
            f'    <span style="color:#374151; font-weight:500;">#{rank_i} {lbl}</span>'
            f'    <span style="color:#0f172a; font-weight:600;">{val:.3f}</span>'
            f'  </div>'
            f'  <div style="height:4px; background:#eef0f3;'
            f'    border-radius:2px; margin-top:4px;">'
            f'    <div style="height:4px; border-radius:2px; width:{bar:.0f}%;'
            f'    background:#2563eb;"></div>'
            f'  </div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    st.markdown(
        '<div style="font-size:0.7rem; color:#9ca3af; margin-top:12px; line-height:1.6;">'
        'Чем выше |SHAP|, тем сильнее фактор влияет на предсказание риска отчисления.</div>',
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)
