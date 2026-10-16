"""Concept page for directions without data: description, what exists, what to collect. No numbers."""
from __future__ import annotations

import streamlit as st

from components import ui
from src.advisor.facts.registry import registry


def render(key: str, title: str, description: str, would_show: list[str]) -> None:
    reg = registry()
    ui.page_header(title, "Направление описано, но не реализовано: данных в системе нет.", status="концепция")
    ui.data_mode_banner(f"{ui.badge_html('нет данных')} Здесь нет ни одного числа: модуль не реализован. "
                        "Советник по этому направлению отвечает «нет данных» и перечисляет, что нужно собрать.")
    c1, c2 = st.columns(2, gap="large")
    with c1:
        with st.container(border=True):
            st.markdown("#### Что это за направление")
            st.write(description)
            st.markdown("#### Что система умеет сейчас")
            st.write(reg.get(f"system.capability.{key}.can")["value"])
            st.markdown("#### Чего не умеет")
            st.write(reg.get(f"system.capability.{key}.cannot")["value"])
    with c2:
        with st.container(border=True):
            st.markdown("#### Какие данные нужно собрать")
            for item in reg.get(f"system.needed_data.{key}")["value"].split("; "):
                st.markdown(f"- {item}")
            st.markdown("#### Что появится, когда данные будут")
            for item in would_show:
                st.markdown(f"- {item}")
    ui.caveat("Показатели появятся только после сбора данных и проверки по той же схеме, что в других модулях: "
              "реестр фактов, статус, источник, оговорка.", title="Как будет устроено")
