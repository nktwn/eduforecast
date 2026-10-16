import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import io
import streamlit as st
from components.charts import reliability_chart
from components.data_loader import (
    DATA_DIR as OULAD_DIR, FACULTY_MAP, K_OPTIONS, RISK_LABELS_RU, RESULT_RU,
    get_risk_week, train_risk_model,
)
from components.styles import GLASS_CSS, demo_data_banner, require_data, sidebar_logo

RISK_GROUP_RU = {"HIGH": "Высокий (топ-10%)", "MEDIUM": "Средний (следующие 20%)", "LOW": "Низкий"}

st.set_page_config(
    page_title="Студенты | EduForecast-SIS",
    page_icon="А",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(GLASS_CSS, unsafe_allow_html=True)
require_data([OULAD_DIR / f for f in ("studentInfo.csv", "studentVle.csv", "studentAssessment.csv", "assessments.csv", "studentRegistration.csv")], "Подготовка данных → Academic (OULAD)")
demo_data_banner()
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

k = st.radio(
    "Неделя прогноза k",
    options=list(K_OPTIONS),
    index=list(K_OPTIONS).index(get_risk_week()),
    format_func=lambda w: f"Неделя {w}",
    horizontal=True,
    help="Модель видит только данные до конца недели k (клики и сданные задания) "
         "и демографию при регистрации. Выбор действует на всех страницах Academic.",
)
st.session_state["risk_week"] = k

with st.spinner("Анализ рисков студентов..."):
    df, quality, _, _ = train_risk_model(selected_code, k)

total = len(df)
qf, qa = quality["faculty"], quality["overall"]

st.markdown(
    f'<div style="font-size:0.82rem; color:#6b7280; margin:4px 0 14px 0;">'
    f'Риск показан для {total:,} студентов, ещё не отчисленных к концу недели {k}. '
    f'Ещё {quality["n_left_by_k"]:,} из {quality["n_registered"]:,} регистраций '
    f'к этому моменту уже ушли и в прогноз не входят. Каждый риск предсказан моделью, '
    f'которая этого студента не видела (GroupKFold по студенту).</div>',
    unsafe_allow_html=True,
)

st.markdown(
    f'<div class="section-title">Качество модели на неделе {k}</div>',
    unsafe_allow_html=True,
)
m1, m2, m3, m4 = st.columns(4)
m1.metric("AUC", f'{qf["auc"]:.2f}', help="Площадь под ROC-кривой среди ещё учащихся; 0.5 — случайное угадывание.")
m2.metric("Precision в топ-10%", f'{qf["precision_top10"]:.0%}',
          help="Доля реально ушедших среди 10% студентов с наибольшим риском.")
m3.metric("Охват в топ-10%", f'{qf["recall_top10"]:.0%}',
          help="Какая доля всех ушедших попала в топ-10% по риску.")
m4.metric("Brier score", f'{qf["brier"]:.3f}', help="Средний квадрат ошибки вероятности; меньше — лучше.")
st.caption(
    f'Оценка на данных OULAD (демо), вне обучающей выборки, среди ещё учащихся на неделе {k}: '
    f'{qf["n"]:,} студентов, из них ушли позже {qf["positives"]:,} ({qf["base_rate"]:.0%}). '
    f'По всем факультетам: AUC {qa["auc"]:.2f}, precision в топ-10% {qa["precision_top10"]:.0%}, '
    f'охват {qa["recall_top10"]:.0%}, Brier {qa["brier"]:.3f}. '
    f'Группы риска заданы по перцентилям внутри факультета: высокий — топ-10%, средний — следующие 20%, '
    f'низкий — остальные. AUC умеренный, поэтому «высокий» значит «выше, чем у остальных», '
    f'а не «скорее всего уйдёт».'
)
with st.expander("Калибровка вероятностей"):
    st.plotly_chart(
        reliability_chart(quality["reliability"], f"График надёжности, все факультеты, неделя {k}"),
        width="stretch", config={"displayModeBar": False},
    )
    st.caption(
        "Точки — децили прогноза: средний предсказанный риск и доля реально ушедших. "
        "Близость к диагонали значит, что «20%» действительно соответствует примерно 20% ушедших. "
        "Модель без дополнительной калибровки: калибровка Платта и изотоническая на отдельном фолде "
        "Brier не улучшали (audit/academic/risk_model_eval.py)."
    )

st.markdown("<br>", unsafe_allow_html=True)

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
        format_func=lambda x: RISK_GROUP_RU.get(x, x),
    )
with fc2:
    result_options = sorted(df["final_result"].unique().tolist())
    result_filter = st.multiselect(
        "Итог курса (факт)",
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
    "code_presentation": "Поток",
    "risk_level": "Риск",
    "risk_score_pct": "Скор (%)",
    "top_risk_reason": "Главная причина",
    "avg_score": "Балл",
    "total_clicks": "Активность",
    "assessments_submitted": "Заданий",
    "final_result": "Статус",
}
table = filtered[list(col_map)].rename(columns=col_map).copy()
st.caption(f"Балл, активность (клики) и задания — только до конца недели {k}. "
           "Статус — фактический итог курса, показан для проверки прогноза на демо-данных.")
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
    width="stretch",
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
    (s1, "HIGH",   "#dc2626", "Высокий риск (топ-10%)"),
    (s2, "MEDIUM", "#d97706", "Средний риск (следующие 20%)"),
    (s3, "LOW",    "#059669", "Низкий риск (остальные 70%)"),
]:
    cnt   = int((df["risk_level"] == level).sum())
    pct   = cnt / total * 100 if total else 0
    avg_s = df[df["risk_level"] == level]["avg_score"].mean()
    avg_c = df[df["risk_level"] == level]["total_clicks"].mean()
    left  = df.loc[df["risk_level"] == level, "is_withdrawn"].mean()
    with col:
        st.markdown(
            f'<div class="risk-summary-card" style="border-left:3px solid {border};">'
            f'  <div style="font-size:0.8rem; color:#6b7280; margin-bottom:2px;">{label}</div>'
            f'  <div style="font-size:1.8rem; font-weight:700; color:#0f172a;">{cnt}</div>'
            f'  <div style="font-size:0.8rem; color:#9ca3af; margin-top:2px;">{pct:.1f}% студентов · '
            f'фактически ушли {left:.0%}</div>'
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
