# The look now comes from components/theme.py (CSS variables, light/dark); kept for page compatibility.
GLASS_CSS = ""


def _advisor_model() -> str:
    try:
        from src.advisor.config import load_settings
        return load_settings().model
    except Exception:
        return "не настроена"


def sidebar_logo(selected_code, faculty_map):
    """Faculty selector for the Academic pages (brand and status live in components/shell.py)."""
    import streamlit as st
    with st.sidebar:
        code = st.selectbox(
            "Факультет (условный, OULAD)",
            options=list(faculty_map.keys()),
            format_func=lambda x: f"{x} — {faculty_map[x]}",
            index=list(faculty_map.keys()).index(selected_code)
                  if selected_code in faculty_map else 0,
            key="selected_faculty",
        )
        st.caption("Демо-данные Open University (Великобритания), факультеты условные. Модель: риск на неделе k "
                   "по данным недель ≤ k, оценка вне обучающей выборки (случайный лес + SHAP). "
                   f"ИИ: {_advisor_model()}.")
    return code


DEMO_DATA_NOTE = ("Демо-данные: открытый набор OULAD (Open University, UK), названия факультетов условные.")


def demo_data_banner():
    import streamlit as st
    st.markdown(f'<div class="ef-banner">{DEMO_DATA_NOTE}</div>', unsafe_allow_html=True)


def sidebar_brand(subtitle: str, footer_html: str):
    """Module note in the sidebar (brand and status live in components/shell.py)."""
    import streamlit as st
    with st.sidebar:
        st.markdown(f'<div class="ef-muted" style="font-size:0.78rem;line-height:1.7"><b>{subtitle}</b><br>'
                    f'{footer_html}</div>', unsafe_allow_html=True)


def require_data(paths, readme_section: str, hint: str = ""):
    import streamlit as st
    missing = [p for p in paths if not p.exists()]
    if not missing:
        return
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    names = ", ".join(f"`{p.resolve().relative_to(root) if p.resolve().is_relative_to(root) else p}`" for p in missing[:4])
    st.error(f"**Данные не найдены:** {names}. См. README, раздел «{readme_section}». {hint}")
    st.stop()
