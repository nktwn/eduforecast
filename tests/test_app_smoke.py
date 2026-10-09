from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "app"
PAGES = ["home.py", "pages/01_Students.py", "pages/02_Analytics.py", "pages/03_AI_Advisor.py",
         "pages/04_Research.py", "pages/05_Finance.py"]


def run(page: str) -> AppTest:
    at = AppTest.from_file(str(APP / page), default_timeout=300)
    at.run()
    return at


@pytest.mark.parametrize("page", PAGES)
def test_page_renders_without_exception(page):
    at = run(page)
    assert not at.exception, [e.value for e in at.exception]


def test_research_page_shows_backtest():
    at = run("pages/04_Research.py")
    texts = " ".join(m.value for m in at.markdown)
    assert "606" in texts


def test_finance_mock_mode_works_without_data():
    at = run("pages/05_Finance.py")
    at.radio(key="fin_provider").set_value("mock").run()
    assert not at.exception
    assert "Мок-данные" in " ".join(m.value for m in at.markdown)
