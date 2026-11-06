import sys
import time
from pathlib import Path

for _p in (Path(__file__).resolve().parents[1], Path(__file__).resolve().parents[2]):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import streamlit as st  # noqa: E402

from components import theme, ui  # noqa: E402
from components.shell import current_role, key_status_cached  # noqa: E402
from src.advisor.briefing import to_html, to_markdown  # noqa: E402
from src.advisor.config import load_settings  # noqa: E402
from src.advisor.core import Advisor  # noqa: E402
from src.advisor.facts.registry import registry  # noqa: E402
from src.advisor.roles import ROLES  # noqa: E402

FACULTIES = ["all", "aaa", "bbb", "ccc", "ddd", "eee", "fff", "ggg"]
SETTINGS = load_settings()
KEY = key_status_cached(SETTINGS.base_url, SETTINGS.model, SETTINGS.has_key)


@st.cache_resource(show_spinner=False)
def get_advisor(model: str, base_url: str, has_key: bool) -> Advisor:
    return Advisor()


ADV = get_advisor(SETTINGS.model, SETTINGS.base_url, SETTINGS.has_key)
REG = registry()
role = current_role()

ui.page_header("ИИ-советник", f"Роль: {ROLES[role].name}. Каждое число в ответе — из реестра фактов, со статусом и "
                              "источником; неподтверждённый ответ не показывается.")
if KEY == "есть":
    ui.data_mode_banner(f"LLM: <b>{ui.esc(SETTINGS.model)}</b>. Советник видит только агрегаты (группы не меньше 30 "
                        "студентов) и не выносит решений по конкретным людям.")
else:
    ui.data_mode_banner(f"Ключ LLM: <b>{ui.esc(KEY)}</b>. Доступен брифинг по роли без LLM; ответы на свободные "
                        "вопросы — после настройки ключа (см. «Настройки и состояние»).")

c1, c2, _ = st.columns([1, 1, 3])
k = c1.selectbox("Неделя прогноза k", [5, 10, 20], index=[5, 10, 20].index(st.session_state.get("risk_week", 5)),
                 help=ui.GLOSSARY["k"])
faculty = c2.selectbox("Факультет (OULAD)", FACULTIES, format_func=lambda f: "все" if f == "all" else f.upper())

tab_brief, tab_q = st.tabs(["Брифинг по роли", "Вопросы"])

with tab_brief:
    st.caption("Брифинг собирается из шаблонов и фактов без LLM: работает и без ключа.")
    if st.button("Сформировать брифинг", type="primary", key="brief_btn"):
        st.session_state["brief"] = {"role": role, "k": k, "cards": ADV.briefing(role, k)}
    brief = st.session_state.get("brief")
    if brief and brief["role"] == role:
        cards = brief["cards"]
        d1, d2, _ = st.columns([1, 1, 3])
        d1.download_button("Скачать Markdown", to_markdown(cards, role, REG.built_at),
                           file_name=f"briefing_{role}.md", mime="text/markdown")
        d2.download_button("Печатная версия (HTML)", to_html(cards, role, REG.built_at),
                           file_name=f"briefing_{role}.html", mime="text/html")
        cols = st.columns(2, gap="medium")
        for i, card in enumerate(cards):
            with cols[i % 2]:
                ui.advice_card(card)
    else:
        ui.empty_state("Брифинг ещё не сформирован", " Нажмите кнопку — отчёт займёт несколько секунд.")


def as_markdown(answer: dict) -> str:
    parts = [f"**Наблюдение.** {answer['observation']}"]
    if answer.get("needed_data"):
        parts.append(f"**Что нужно собрать.** {answer['needed_data']}")
    parts += [f"**Рекомендация.** {answer['recommendation']}", f"**Риски и ограничения.** {answer['risks']}"]
    return "\n\n".join(parts)


def stream(text: str):
    for word in text.split(" "):
        yield word + " "
        time.sleep(0.012)


def show_entry(entry: dict, animate: bool = False) -> None:
    with st.chat_message("user"):
        st.write(entry["q"])
    with st.chat_message("assistant"):
        a = entry.get("answer")
        if not a:
            st.error(entry.get("error") or "Ответ не получен.")
            if entry.get("mode") == "offline":
                st.caption("Откройте вкладку «Брифинг по роли».")
            return
        if animate:
            st.write_stream(stream(as_markdown(a)))
        else:
            st.markdown(as_markdown(a))
        st.markdown(f"**Надёжность:** {ui.badge_html(a['reliability'])} "
                    f"<span class='ef-muted'>· режим: {ui.esc(entry['mode'])}</span>", unsafe_allow_html=True)
        if a.get("warning"):
            ui.caveat(a["warning"], title="Внимание")


with tab_q:
    history = st.session_state.setdefault("chat", {}).setdefault(role, [])
    left, right = st.columns([1.7, 1], gap="large")
    with left:
        qq = ROLES[role].quick_questions
        qcols = st.columns(len(qq))
        clicked = None
        for i, (c, q) in enumerate(zip(qcols, qq)):
            if c.button(q, key=f"qq_{role}_{i}", width="stretch"):
                clicked = q
        chat_box = st.container(height=520, border=True)
        with chat_box:
            if not history:
                ui.empty_state("Задайте вопрос", " Например, выберите быстрый вопрос выше.")
            for entry in history:
                show_entry(entry)
        prompt = st.chat_input("Вопрос советнику", key=f"chat_input_{role}")
        question = st.session_state.pop("advisor_prefill", None) or clicked or prompt
        if question:
            with chat_box:
                with st.status("Советник работает…", expanded=False) as status:
                    res = ADV.ask(question, role, k=k, faculty=faculty,
                                  on_event=lambda m: status.update(label=m))
                    status.update(label="Готово" if res.ok else "Ответ не получен",
                                  state="complete" if res.ok else "error")
                entry = {"q": question, "answer": res.answer, "error": res.error, "mode": res.mode,
                         "tools": [t["name"] for t in res.tools_called]}
                show_entry(entry, animate=True)
            history.append(entry)
    with right:
        st.markdown('<div class="section-title" style="margin-top:0">Основания</div>', unsafe_allow_html=True)
        last = next((e for e in reversed(history) if e.get("answer")), None)
        if last is None:
            ui.empty_state("Пока нет ответа", " Здесь появятся факты, на которые опирается ответ.")
        else:
            a = last["answer"]
            if a.get("warning"):
                ui.caveat(a["warning"], title="Внимание")
            if last.get("tools"):
                st.caption("Инструменты: " + ", ".join(last["tools"]))
            if a["facts"]:
                ui.evidence_panel(a["facts"])
            else:
                st.caption("Ответ не опирается на числа из реестра.")
        st.caption(f"Реестр фактов: {theme.num(len(REG.facts))} фактов, собран "
                   f"{theme.ru_date(REG.built_at, with_time=True)}.")
