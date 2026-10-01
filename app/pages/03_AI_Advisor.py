import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import numpy as np
import requests
import streamlit as st
from dotenv import load_dotenv
from components.data_loader import (
    FACULTY_MAP, train_risk_model, compute_health_index, get_faculty_data,
)
from components.styles import GLASS_CSS, sidebar_logo

load_dotenv(Path(__file__).parent.parent.parent / ".env")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_URL     = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL   = "llama-3.3-70b-versatile"

st.set_page_config(
    page_title="AI Советник | EduForecast-SIS",
    page_icon="А",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(GLASS_CSS, unsafe_allow_html=True)
st.markdown("""
<style>
.chat-user {
    background: #eff6ff;
    border: 1px solid #dbeafe;
    border-radius: 8px;
    padding: 10px 14px;
    margin: 8px 0 8px 15%;
    color: #0f172a;
    font-size: 0.9rem;
    line-height: 1.55;
}
.chat-ai {
    background: #ffffff;
    border: 1px solid #e3e6eb;
    border-left: 3px solid #2563eb;
    border-radius: 8px;
    padding: 12px 16px;
    margin: 8px 15% 8px 0;
    color: #0f172a;
    font-size: 0.9rem;
    line-height: 1.6;
}
.chat-label {
    font-size: 0.7rem; font-weight: 600;
    color: #9ca3af;
    margin-bottom: 3px;
}
.context-ribbon {
    background: #ffffff;
    border: 1px solid #e3e6eb;
    border-radius: 8px;
    padding: 10px 16px;
    font-size: 0.8rem;
    color: #374151;
    margin-bottom: 16px;
    display: flex; gap: 10px; flex-wrap: wrap; align-items: center;
}
.ctx-chip {
    background: #f5f6f8;
    border: 1px solid #e3e6eb;
    border-radius: 6px;
    padding: 3px 10px;
    font-size: 0.75rem;
    font-weight: 500;
    color: #374151;
    white-space: nowrap;
}
.empty-chat {
    text-align: center; padding: 50px 20px;
    color: #9ca3af;
}
</style>
""", unsafe_allow_html=True)

selected_code = st.session_state.get("selected_faculty", "AAA")
selected_code = sidebar_logo(selected_code, FACULTY_MAP)
faculty_name  = FACULTY_MAP[selected_code]

st.markdown(
    f'<h1 style="margin:0 0 4px 0; font-size:1.7rem;">ИИ Советник</h1>'
    f'<p style="color:#9ca3af; margin:0 0 18px 0; font-size:0.85rem;">'
    f'{faculty_name} · Llama 3.3 70B</p>',
    unsafe_allow_html=True,
)

with st.spinner("Подготовка контекста..."):
    df_raw              = get_faculty_data(selected_code)
    df_model, _, fc, sv = train_risk_model(selected_code)

total       = len(df_model)
high        = int((df_model["risk_level"] == "HIGH").sum())
medium      = int((df_model["risk_level"] == "MEDIUM").sum())
low         = int((df_model["risk_level"] == "LOW").sum())
avg_score   = df_raw["avg_score"].mean()
avg_clicks  = df_raw["total_clicks"].mean()
health      = compute_health_index(df_raw)
w_pct       = (df_raw["final_result"] == "Withdrawn").mean() * 100

feat_labels = {
    "total_clicks":"Активность в LMS", "active_days":"Активные дни",
    "assessments_submitted":"Задания", "avg_score":"Средний балл",
    "min_score":"Мин. балл", "num_of_prev_attempts":"Повт. попытки",
    "studied_credits":"Нагрузка", "unregistered":"Регистрация",
    "edu_enc":"Образование", "imd_enc":"Соц. фактор", "age_enc":"Возраст",
}
mean_shap = np.abs(sv).mean(axis=0)
top3 = [feat_labels.get(fc[i], fc[i]) for i in np.argsort(mean_shap)[::-1][:3]]

st.markdown(
    f'<div class="context-ribbon">'
    f'  <span style="font-weight:600; color:#6b7280;">Контекст:</span>'
    f'  <span class="ctx-chip">{total} студентов</span>'
    f'  <span class="ctx-chip" style="color:#dc2626;">Высокий риск: {high} ({high/total*100:.1f}%)</span>'
    f'  <span class="ctx-chip">Балл: {avg_score:.1f}</span>'
    f'  <span class="ctx-chip">Здоровье: {health:.0f}/100</span>'
    f'  <span class="ctx-chip">{", ".join(top3[:2])}</span>'
    f'</div>',
    unsafe_allow_html=True,
)

SYSTEM_PROMPT = f"""Ты — AI советник декана {faculty_name} в Astana IT University.
У тебя есть доступ к актуальным аналитическим данным факультета из LMS.

ДАННЫЕ ФАКУЛЬТЕТА:
- Всего студентов: {total}
- Высокий риск отчисления: {high} ({high/total*100:.1f}%)
- Средний риск: {medium} ({medium/total*100:.1f}%)
- Низкий риск (стабильные): {low} ({low/total*100:.1f}%)
- Отчислено/отказались: {w_pct:.1f}%
- Средний балл: {avg_score:.1f}/100
- Средняя активность (кликов/студент): {avg_clicks:.0f}
- Индекс здоровья факультета: {health:.0f}/100
- Топ-3 фактора риска (SHAP): {", ".join(top3)}

ПРАВИЛА:
1. Отвечай ТОЛЬКО на русском языке
2. Используй конкретные цифры из данных выше
3. Давай 2-4 конкретных, измеримых рекомендации
4. Максимум 4 абзаца, без воды
5. Фокусируйся на действиях которые декан может предпринять сейчас
6. При вопросах об отдельных студентах — уточни что работаешь с агрегированными данными"""

def call_groq(messages: list) -> str:
    if not GROQ_API_KEY:
        return "GROQ_API_KEY не задан. Добавьте ключ в файл .env"
    try:
        r = requests.post(
            GROQ_URL,
            json={"model": GROQ_MODEL, "messages": messages,
                  "temperature": 0.7, "max_tokens": 1024},
            headers={"Authorization": f"Bearer {GROQ_API_KEY}",
                     "Content-Type": "application/json"},
            timeout=30,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except requests.exceptions.Timeout:
        return "Превышено время ожидания. Попробуйте снова."
    except requests.exceptions.HTTPError:
        code = r.status_code if r else "?"
        return f"Ошибка API ({code}). Проверьте GROQ_API_KEY в .env"
    except Exception as e:
        return f"Ошибка: {e}"

SUGGESTIONS = [
    "Какова главная проблема факультета?",
    "Как снизить процент отчислений?",
    "Что делать со студентами высокого риска?",
    "Как улучшить успеваемость?",
    "Сравни факультет с нормой",
]

st.markdown("**Быстрые вопросы:**")
sug_cols = st.columns(len(SUGGESTIONS))
clicked_sug = None
for i, (c, sug) in enumerate(zip(sug_cols, SUGGESTIONS)):
    with c:
        if st.button(sug, key=f"s{i}", use_container_width=True):
            clicked_sug = sug

ck = f"chat_{selected_code}"
if ck not in st.session_state:
    st.session_state[ck] = []

st.markdown('<div class="glass-card" style="min-height:360px; max-height:520px; overflow-y:auto;">', unsafe_allow_html=True)

if not st.session_state[ck]:
    st.markdown(
        '<div class="empty-chat">'
        ''
        '  <div style="font-weight:600; font-size:0.95rem;">Задайте вопрос декана</div>'
        '  <div style="font-size:0.82rem; margin-top:4px;">Советник ответит на основе реальных данных факультета</div>'
        '</div>',
        unsafe_allow_html=True,
    )
else:
    for msg in st.session_state[ck]:
        if msg["role"] == "user":
            st.markdown(
                f'<div class="chat-label" style="text-align:right; color:#2563eb; margin-right:15%;">Вы</div>'
                f'<div class="chat-user">{msg["content"]}</div>',
                unsafe_allow_html=True,
            )
        else:
            body = msg["content"].replace("\n\n", "<br><br>").replace("\n", "<br>")
            st.markdown(
                f'<div class="chat-label" style="color:#2563eb;">ИИ советник</div>'
                f'<div class="chat-ai">{body}</div>',
                unsafe_allow_html=True,
            )

st.markdown("</div>", unsafe_allow_html=True)

inp_c, btn_c = st.columns([5, 1])
with inp_c:
    user_input = st.text_input(
        "Вопрос",
        value=clicked_sug or "",
        placeholder="Например: Как снизить риск отчислений на факультете?",
        label_visibility="collapsed",
        key="ai_input",
    )
with btn_c:
    send = st.button("Отправить", type="primary", use_container_width=True)

question = (user_input or clicked_sug or "").strip()
if (send or clicked_sug) and question:
    st.session_state[ck].append({"role": "user", "content": question})
    msgs = [{"role": "system", "content": SYSTEM_PROMPT}] + [
        {"role": m["role"], "content": m["content"]} for m in st.session_state[ck]
    ]
    with st.spinner("AI анализирует данные..."):
        ans = call_groq(msgs)
    st.session_state[ck].append({"role": "assistant", "content": ans})
    st.rerun()

cl1, cl2 = st.columns([1, 3])
with cl1:
    if st.session_state[ck]:
        if st.button("Очистить историю", use_container_width=True):
            st.session_state[ck] = []
            st.rerun()

with st.expander("Данные, переданные ИИ советнику", expanded=False):
    st.markdown(f"""
**Факультет:** {faculty_name}

| Показатель | Значение |
|---|---|
| Всего студентов | {total} |
| Высокий риск | {high} ({high/total*100:.1f}%) |
| Средний риск | {medium} ({medium/total*100:.1f}%) |
| Низкий риск | {low} ({low/total*100:.1f}%) |
| Отчислено | {w_pct:.1f}% |
| Средний балл | {avg_score:.1f}/100 |
| Индекс здоровья | {health:.0f}/100 |
| Топ факторы риска | {", ".join(top3)} |
    """)
