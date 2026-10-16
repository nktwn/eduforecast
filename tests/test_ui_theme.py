"""Design system: WCAG AA contrast of the palette, config.toml in sync, Russian formatting."""
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from components.theme import PALETTES, STATUS_STYLE, contrast, num, pct, ru_date  # noqa: E402

TEXT_PAIRS = [("text", "bg"), ("text", "surface"), ("text_2", "surface"), ("muted", "surface"), ("muted", "bg"),
              ("muted", "surface_2"), ("primary", "surface"), ("primary", "bg"), ("danger", "surface"),
              ("warn", "surface"), ("text", "warn_bg"), ("text", "surface_2")]


def test_palette_contrast_wcag_aa():
    for mode, p in PALETTES.items():
        for fg, bg in TEXT_PAIRS + list(STATUS_STYLE.values()):
            assert contrast(p[fg], p[bg]) >= 4.5, (mode, fg, bg, round(contrast(p[fg], p[bg]), 2))


def test_streamlit_config_matches_palette():
    cfg = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8"))
    for mode in ("light", "dark"):
        t, p = cfg["theme"][mode], PALETTES[mode]
        assert t["backgroundColor"] == p["bg"] and t["textColor"] == p["text"] and t["primaryColor"] == p["accent"]
        assert contrast(t["textColor"], t["backgroundColor"]) >= 4.5
        assert contrast(t["primaryColor"], "#ffffff") >= 4.5  # white text on buttons and chips
        assert contrast(t["linkColor"], t["backgroundColor"]) >= 4.5


def test_russian_format():
    assert num(1234567) == "1 234 567"
    assert pct(0.1234) == "12,3%" and pct(0.05, signed=True) == "+5,0%"
    assert ru_date("2026-10-16T12:00:00+00:00") == "16 октября 2026"
