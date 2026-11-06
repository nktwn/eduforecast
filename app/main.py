import sys
from pathlib import Path

APP = Path(__file__).resolve().parent
for p in (APP, APP.parent):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import streamlit as st  # noqa: E402

st.set_page_config(page_title="EduForecast-SIS", page_icon=":material/school:", layout="wide",
                   initial_sidebar_state="auto")

from components import shell, ui  # noqa: E402

ui.inject_css()


def page(path: str, **kw):
    """A page is listed only if its file exists (keeps navigation valid while pages are added)."""
    return st.Page(path, **kw) if (APP / path).exists() else None


PAGES = {
    "": [page("pages/00_Command_Center.py", title="Командный центр", icon=":material/dashboard:",
                 url_path="command-center", default=True)],
    "Направления": [
        page("home.py", title="Академический: обзор", icon=":material/school:", url_path="academic"),
        page("pages/01_Students.py", title="Академический: студенты", icon=":material/groups:",
                url_path="Students"),
        page("pages/02_Analytics.py", title="Академический: аналитика", icon=":material/insights:",
                url_path="Analytics"),
        page("pages/04_Research.py", title="Научный", icon=":material/science:", url_path="Research"),
        page("pages/05_Finance.py", title="Финансы", icon=":material/account_balance:", url_path="Finance"),
        page("pages/06_International.py", title="Международный", icon=":material/public:",
                url_path="international"),
        page("pages/07_Upbringing.py", title="Воспитательный", icon=":material/diversity_3:",
                url_path="upbringing"),
    ],
    "Советник и методика": [
        page("pages/03_AI_Advisor.py", title="ИИ-советник", icon=":material/smart_toy:", url_path="AI_Advisor"),
        page("pages/08_Verified.py", title="Что проверено", icon=":material/fact_check:", url_path="verified"),
        page("pages/09_Settings.py", title="Настройки и состояние", icon=":material/settings:",
                url_path="settings"),
    ],
}
navigation = st.navigation({k: [p for p in v if p is not None] for k, v in PAGES.items()})
shell.sidebar()
navigation.run()
