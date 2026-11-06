"""App shell: sidebar with role, data and key status (one place for every page)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from components import theme  # noqa: E402
from components.ui import badge_html, esc  # noqa: E402
from src.advisor.config import load_settings  # noqa: E402
from src.advisor.facts.registry import registry  # noqa: E402
from src.advisor.roles import DEFAULT_ROLE, ROLES  # noqa: E402

DATA_CHECKS = {
    "Academic (OULAD)": ROOT / "data" / "raw" / "studentInfo.csv",
    "Research (OpenAlex)": ROOT / "data" / "research" / "raw" / "yearly_work_counts_I4405257690.json",
    "Finance (IPEDS)": ROOT / "data" / "finance" / "panel_stage2.parquet",
    "Профиль AITU": ROOT / "data" / "aitu" / "financials_2019_2020.csv",
}


@st.cache_data(ttl=600, show_spinner=False)
def key_status_cached(base_url: str, model: str, has_key: bool) -> str:
    from src.advisor.llm import key_status

    return key_status(load_settings()) if has_key else "нет"


def current_role() -> str:
    role = st.session_state.get("role", DEFAULT_ROLE)
    return role if role in ROLES else DEFAULT_ROLE


def sidebar() -> str:
    with st.sidebar:
        st.markdown('<div style="font-weight:800;font-size:1.05rem">EduForecast-SIS</div>'
                    '<div class="ef-muted" style="font-size:0.78rem;margin-bottom:8px">Аналитика и советник '
                    'для руководства вуза</div>', unsafe_allow_html=True)
        ids = list(ROLES)
        st.selectbox("Роль", ids, index=ids.index(current_role()), format_func=lambda r: ROLES[r].name,
                     key="role")
        s = load_settings()
        status = key_status_cached(s.base_url, s.model, s.has_key)
        p = theme.palette()
        color = {"есть": p["ok"], "нет": p["muted"], "недействителен": p["danger"]}.get(status, p["warn"])
        reg = registry()
        rows = "".join(f'<div>{"●" if path.exists() else "○"} {esc(name)}</div>' for name, path in DATA_CHECKS.items())
        st.markdown(
            f'<div style="font-size:0.78rem;line-height:1.7;margin-top:6px">'
            f'<div><b>Ключ LLM:</b> <span style="color:{color};font-weight:700">{esc(status)}</span> · '
            f'{esc(s.model)}</div><div><b>Реестр фактов:</b> {len(reg.facts)} · '
            f'{esc(theme.ru_date(reg.built_at, with_time=True))}</div>'
            f'<div style="margin-top:6px"><b>Данные</b> (● есть, ○ нет):</div>{rows}</div>',
            unsafe_allow_html=True)
    return current_role()


def status_line(statuses: list[str]) -> str:
    return " ".join(badge_html(s) for s in statuses)
