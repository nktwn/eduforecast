import sys
from pathlib import Path

for _p in (Path(__file__).resolve().parents[1], Path(__file__).resolve().parents[2]):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import streamlit as st  # noqa: E402

from components import ui  # noqa: E402
from components.shell import current_role  # noqa: E402
from src.advisor.facts.registry import registry  # noqa: E402
from src.advisor.roles import ROLES  # noqa: E402

REG = registry()
ROLE_KPIS = {
    "rector": ["academic.risk.k5.all.auc", "research.aitu.works.y2025", "finance.criterion.retention_rate.passed",
               "aitu.y2020.current_ratio"],
    "vp_academic": ["academic.risk.k5.all.auc", "academic.risk.k5.all.precision_top10",
                    "academic.risk.k5.all.recall_top10", "academic.risk.k20.all.auc"],
    "vp_research": ["research.aitu.works.y2025", "research.aitu.works.y2024", "research.panel.works_count.best_gain",
                    "research.panel.intl_collab_share.passed"],
    "vp_finance": ["aitu.y2020.share_state_order_in_revenue", "aitu.y2020.current_ratio",
                   "aitu.y2020.share_payroll_with_social_in_expenses.excl_one_off",
                   "finance.criterion.retention_rate.excluding_flagged.gain"],
    "vp_international": ["system.module.international.status", "research.panel.intl_collab_share.passed",
                         "research.panel.intl_collab_share.best_gain", "system.module.upbringing.status"],
    "vp_digital": ["system.module.academic.status", "system.module.research.status", "system.module.finance.status",
                   "system.module.digital.status"],
}
MODULES = [("academic", "Академический"), ("research", "Научный"), ("finance", "Финансы"),
           ("international", "Международный"), ("upbringing", "Воспитательный"), ("digital", "Цифровизация")]
LIGHT_LABEL = {"проверено": "проверено", "демо": "демо-данные", "исследовательское": "исследовательское",
               "нет данных": "нет данных"}


def _set_role():
    st.session_state["role"] = st.session_state["cc_role"]


role = current_role()
ui.page_header("Командный центр", f"Сводка для роли «{ROLES[role].name}». Все числа — из реестра фактов, у каждого "
                                  "указан статус.")
ids = list(ROLES)
st.segmented_control("Роль", ids, default=role, format_func=lambda r: ROLES[r].name, key="cc_role",
                     on_change=_set_role, label_visibility="collapsed")

st.markdown('<div class="section-title">Ключевые показатели</div>', unsafe_allow_html=True)
cols = st.columns(4)
for col, fid in zip(cols, ROLE_KPIS[role]):
    f = REG.get(fid)
    with col:
        if f is None:
            ui.kpi_card(fid, "нет данных", "нет данных")
            continue
        hint = f"{ui.esc(f['period'])}. {ui.esc(f['caveat'].split('. ')[0])}."
        ui.kpi_card(f["metric"], REG.display(fid), f["status"], hint=hint, help_text=f["caveat"])

left, right = st.columns([1, 1.25], gap="large")
with left:
    st.markdown('<div class="section-title">Готовность модулей</div>', unsafe_allow_html=True)
    for key, name in MODULES:
        status = REG.get(f"system.module.{key}.status")["value"]
        can = REG.get(f"system.capability.{key}.can")["value"]
        st.markdown(f'{ui.light(status)}**{name}** — {ui.badge_html(status)}<br>'
                    f'<span class="ef-muted" style="font-size:0.84rem">{ui.esc(can)}</span>', unsafe_allow_html=True)
with right:
    st.markdown('<div class="section-title">Что требует внимания</div>', unsafe_allow_html=True)
    mods = set(ROLES[role].modules)
    items = [f for f in REG.attention() if f["module"] in mods or role == "rector"]
    if not items:
        ui.empty_state("Нет отмеченных фактов для этой роли", " Сигналы появляются из реестра фактов.")
    seen = set()
    for f in items:
        key = f["metric"]
        if key in seen:
            continue
        seen.add(key)
        st.markdown(f'{ui.badge_html(f["status"])} **{ui.esc(f["metric"])}**: {ui.esc(REG.display(f["id"]))} '
                    f'<span class="ef-muted">· {ui.esc(f["period"])}</span>', unsafe_allow_html=True)
    if any(f["status"] != "проверено" for f in items):
        ui.caveat("Часть сигналов основана на исследовательских данных (снимок отчётности AITU с отсканированного "
                  "PDF). Перед решениями сверьте с первоисточником.")

st.markdown('<div class="section-title">Спросить советника</div>', unsafe_allow_html=True)
qcols = st.columns(len(ROLES[role].quick_questions))
for i, (c, q) in enumerate(zip(qcols, ROLES[role].quick_questions)):
    with c:
        if st.button(q, key=f"cc_q{i}", width="stretch"):
            st.session_state["advisor_prefill"] = q
            st.switch_page("pages/03_AI_Advisor.py")
st.caption("Советник отвечает только числами из реестра фактов и показывает основания; без ключа LLM доступен "
           "брифинг по роли.")
