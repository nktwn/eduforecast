"""Every page renders without exceptions: with a key, without a key, without data; plus the app entry point."""
import sys
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "app"
for _p in (APP, APP.parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

PAGES = ["pages/00_Command_Center.py", "home.py", "pages/01_Students.py", "pages/02_Analytics.py",
         "pages/03_AI_Advisor.py", "pages/04_Research.py", "pages/05_Finance.py", "pages/06_International.py",
         "pages/07_Upbringing.py", "pages/08_Verified.py", "pages/09_Settings.py"]


def run(page: str) -> AppTest:
    at = AppTest.from_file(str(APP / page), default_timeout=300)
    at.run()
    return at


@pytest.fixture
def no_key(monkeypatch):
    for name in ("GROQ_API_KEY", "ADVISOR_API_KEY"):
        monkeypatch.setenv(name, "")
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)
    from components import shell
    shell.key_status_cached.clear()


@pytest.fixture
def fake_key(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key-not-real")
    monkeypatch.setenv("ADVISOR_BASE_URL", "http://127.0.0.1:9/v1")  # nothing listens: no real network call
    from components import shell
    shell.key_status_cached.clear()


@pytest.fixture
def no_data(monkeypatch, tmp_path, no_key):
    import src.research.config as rc
    from components import app_cache, data_loader, finance_data_loader, shell

    monkeypatch.setattr(data_loader, "DATA_DIR", tmp_path / "raw")
    monkeypatch.setattr(app_cache, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(rc, "RAW_DIR", tmp_path / "research")
    monkeypatch.setattr(finance_data_loader, "REQUIRED",
                        {k: [tmp_path / "missing.parquet"] if v else [] for k, v in
                         finance_data_loader.REQUIRED.items()})
    monkeypatch.setattr(shell, "DATA_CHECKS", {k: tmp_path / "missing" for k in shell.DATA_CHECKS})
    for fn in (data_loader.load_raw_data, data_loader.train_risk_model, data_loader.get_faculty_data):
        fn.clear()


@pytest.mark.parametrize("page", PAGES)
def test_page_without_key(page, no_key):
    at = run(page)
    assert not at.exception, [e.value for e in at.exception]


@pytest.mark.parametrize("page", PAGES)
def test_page_with_key(page, fake_key):
    at = run(page)
    assert not at.exception, [e.value for e in at.exception]


@pytest.mark.parametrize("page", PAGES)
def test_page_without_data(page, no_data):
    at = run(page)
    assert not at.exception, [e.value for e in at.exception]


def test_app_entry_point_renders_command_center(no_key):
    at = run("main.py")
    assert not at.exception
    assert "Командный центр" in " ".join(m.value for m in at.markdown)


def test_research_page_shows_backtest():
    at = run("pages/04_Research.py")
    texts = " ".join(m.value for m in at.markdown)
    assert "606" in texts


def test_finance_mock_mode_works_without_data(no_data):
    at = run("pages/05_Finance.py")
    at.radio(key="fin_provider").set_value("mock").run()
    assert not at.exception
    assert "Мок-данные" in " ".join(m.value for m in at.markdown)


def test_concept_pages_have_no_numbers():
    import re
    for page in ("pages/06_International.py", "pages/07_Upbringing.py"):
        at = run(page)
        text = " ".join(m.value for m in at.markdown)
        text = re.sub(r"<[^>]+>", " ", text)
        assert not re.search(r"\d+[.,]?\d*\s*%", text), page


def test_advisor_briefing_without_key(no_key):
    at = run("pages/03_AI_Advisor.py")
    at.button(key="brief_btn").click().run()
    assert not at.exception
    text = " ".join(m.value for m in at.markdown)
    assert "Наблюдение" in text and "Надёжность" in text
