import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import io
import streamlit as st
from components.data_loader import FACULTY_MAP, train_risk_model, RISK_COLORS, RISK_LABELS_RU, RESULT_RU
from components.styles import GLASS_CSS, sidebar_logo

st.set_page_config(
    page_title="Студенты | EduForecast-SIS",
    page_icon="А",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(GLASS_CSS, unsafe_allow_html=True)
st.markdown("""
<style>
.top-student-card {
    background: #ffffff;
    border-radius: 8px;
    border: 1px solid #e3e6eb;
    border-top: 3px solid #dc2626;
    padding: 16px 14px;
    text-align: center;
}
.risk-summary-card {
    border-radius: 8px;
    border: 1px solid #e3e6eb;
    padding: 16px 18px;
}
</style>
""", unsafe_allow_html=True)

selected_code = st.session_state.get("selected_faculty", "AAA")
selected_code = sidebar_logo(selected_code, FACULTY_MAP)
faculty_name  = FACULTY_MAP[selected_code]

st.markdown(
    f'<h1 style="margin:0 0 4px 0;">Студенты</h1>'
    f'<p style="color:#6d7280; margin:0 0 22px 0; font-size:0.88rem;">{faculty_name}</p>',
    unsafe_allow_html=True,
)

with st.spinner("Анализ рисков студентов..."):
    df, _, _, _ = train_risk_model(selected_code)

total = len(df)

st.markdown(
    '<div class="section-title">Топ-5 — немедленное внимание</div>',
    unsafe_allow_html=True,
)

top5 = df[df["risk_level"] == "HIGH"].nlargest(5, "risk_score")

if len(top5) == 0:
    st.markdown(
        '<div class="glass-card" style="text-align:center; color:#059669; padding:24px;">'
        '<div style="font-weight:600;">Нет студентов с высоким риском</div>'
        '</div>',
        unsafe_allow_html=True,
    )
else:
    cols = st.columns(min(5, len(top5)))
    for i, (_, row) in enumerate(top5.iterrows()):
        if i < len(cols):
            with cols[i]:
                st.markdown(
                    f'<div class="top-student-card">'
                    f'  <div style="font-weight:700; color:#0f172a; font-size:0.88rem;">'
                    f'    ID {row["id_student"]}</div>'
                    f'  <div style="font-size:1.7rem; font-weight:800; color:#dc2626;'
                    f'    line-height:1; margin:8px 0;">{row["risk_score_pct"]:.0f}%</div>'
                    f'  <div style="font-size:0.68rem; color:#9ca3af; margin-bottom:8px;">'
                    f'    риск отчисления</div>'
                    f'  <div style="font-size:0.72rem; color:#374151; font-weight:500;'
                    f'    background:#f5f6f8; border-radius:6px;'
                    f'    padding:5px 8px; border:1px solid #e3e6eb;">'
                    f'    {row["top_risk_reason"]}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

st.markdown("<br>", unsafe_allow_html=True)

st.markdown('<div class="section-title">Список студентов</div>', unsafe_allow_html=True)

fc1, fc2, fc3 = st.columns([1, 1, 2])
with fc1:
    risk_filter = st.multiselect(
        "Уровень риска",
        options=["HIGH", "MEDIUM", "LOW"],
        default=["HIGH", "MEDIUM", "LOW"],
        format_func=lambda x: RISK_LABELS_RU.get(x, x),
    )
with fc2:
    result_options = sorted(df["final_result"].unique().tolist())
    result_filter = st.multiselect(
        "Статус",
        options=result_options,
        default=result_options,
        format_func=lambda x: RESULT_RU.get(x, x),
    )
with fc3:
    search_id = st.text_input("Поиск по ID студента", placeholder="Введите ID...")

mask = df["risk_level"].isin(risk_filter) & df["final_result"].isin(result_filter)
if search_id.strip():
    try:
        mask = mask & (df["id_student"] == int(search_id.strip()))
    except ValueError:
        pass

filtered = df[mask].copy()

st.markdown(
    f'<div style="font-size:0.82rem; color:#6b7280; margin-bottom:10px;">'
    f'Показано {len(filtered):,} из {total:,} студентов</div>',
    unsafe_allow_html=True,
)

col_map = {
    "id_student": "ID студента",
    "risk_level": "Риск",
    "risk_score_pct": "Скор (%)",
    "top_risk_reason": "Главная причина",
    "avg_score": "Балл",
    "total_clicks": "Активность",
    "assessments_submitted": "Заданий",
    "final_result": "Статус",
}
table = filtered[list(col_map)].rename(columns=col_map).copy()
table["Риск"]   = table["Риск"].map(RISK_LABELS_RU)
table["Статус"] = table["Статус"].map(lambda x: RESULT_RU.get(x, x))
table["Балл"]   = table["Балл"].round(1)

RISK_BG   = {"Высокий": "#FEE2E2", "Средний": "#FEF3C7", "Низкий": "#D1FAE5"}
RISK_TEXT = {"Высокий": "#991B1B",  "Средний": "#92400E", "Низкий": "#065F46"}

def style_risk(v):
    return f"background:{RISK_BG.get(v,'')};color:{RISK_TEXT.get(v,'')};font-weight:700;text-align:center"

def style_score(v):
    if v < 40: return "color:#dc2626;font-weight:700"
    if v < 60: return "color:#d97706;font-weight:600"
    return "color:#059669;font-weight:600"

st.dataframe(
    table.style
        .map(style_risk,  subset=["Риск"])
        .map(style_score, subset=["Балл"])
        .format({"Скор (%)": "{:.1f}%", "Балл": "{:.1f}"}),
    use_container_width=True,
    height=460,
)

buf = io.StringIO()
table.to_csv(buf, index=False, encoding="utf-8-sig")
dc1, _ = st.columns([1, 3])
with dc1:
    st.download_button(
        "Скачать CSV отчёт",
        data=buf.getvalue().encode("utf-8-sig"),
        file_name=f"risk_report_{selected_code}.csv",
        mime="text/csv",
    )

st.markdown("<br>", unsafe_allow_html=True)

st.markdown('<div class="section-title">Сводка по уровням риска</div>', unsafe_allow_html=True)

s1, s2, s3 = st.columns(3)
for col, level, border, label in [
    (s1, "HIGH",   "#dc2626", "Высокий риск"),
    (s2, "MEDIUM", "#d97706", "Средний риск"),
    (s3, "LOW",    "#059669", "Низкий риск"),
]:
    cnt   = int((df["risk_level"] == level).sum())
    pct   = cnt / total * 100 if total else 0
    avg_s = df[df["risk_level"] == level]["avg_score"].mean()
    avg_c = df[df["risk_level"] == level]["total_clicks"].mean()
    with col:
        st.markdown(
            f'<div class="risk-summary-card" style="border-left:3px solid {border};">'
            f'  <div style="font-size:0.8rem; color:#6b7280; margin-bottom:2px;">{label}</div>'
            f'  <div style="font-size:1.8rem; font-weight:700; color:#0f172a;">{cnt}</div>'
            f'  <div style="font-size:0.8rem; color:#9ca3af; margin-top:2px;">{pct:.1f}% студентов</div>'
            f'  <div style="margin-top:10px; display:grid; grid-template-columns:1fr 1fr; gap:8px;">'
            f'    <div style="background:#f5f6f8; border-radius:6px; padding:8px; text-align:center;">'
            f'      <div style="font-size:1.05rem; font-weight:700; color:#0f172a;">{avg_s:.1f}</div>'
            f'      <div style="font-size:0.68rem; color:#9ca3af;">ср. балл</div>'
            f'    </div>'
            f'    <div style="background:#f5f6f8; border-radius:6px; padding:8px; text-align:center;">'
            f'      <div style="font-size:1.05rem; font-weight:700; color:#0f172a;">{avg_c:,.0f}</div>'
            f'      <div style="font-size:0.68rem; color:#9ca3af;">ср. клики</div>'
            f'    </div>'
            f'  </div>'
            f'</div>',
            unsafe_allow_html=True,
        )
