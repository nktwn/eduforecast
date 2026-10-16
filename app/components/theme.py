"""Design tokens: palette (light/dark, WCAG AA), CSS variables, Plotly template, Russian number/date format."""
from __future__ import annotations

import math
from datetime import date, datetime

import plotly.graph_objects as go
import plotly.io as pio

PALETTES = {
    "light": {
        "bg": "#f6f7f9", "surface": "#ffffff", "surface_2": "#f1f3f6", "border": "#d9dde3",
        "text": "#111827", "text_2": "#374151", "muted": "#4b5563", "primary": "#1d4ed8",
        "ok": "#047857", "ok_bg": "#e7f6ef", "research": "#92400e", "research_bg": "#fdf3e1",
        "demo": "#6d28d9", "demo_bg": "#f1ebfd", "nodata": "#4b5563", "nodata_bg": "#eceef1",
        "concept": "#1e40af", "concept_bg": "#e8eefc", "danger": "#b91c1c", "danger_bg": "#fdecec",
        "warn": "#92400e", "warn_bg": "#fdf3e1", "grid": "#e5e8ec",
        "series": ["#1d4ed8", "#b45309", "#047857", "#7c3aed", "#be123c", "#0e7490", "#4d7c0f", "#57534e"],
    },
    "dark": {
        "bg": "#0f1318", "surface": "#171c23", "surface_2": "#1e242d", "border": "#2c333d",
        "text": "#e6e9ee", "text_2": "#c9ced6", "muted": "#a3abb7", "primary": "#7aa7ff",
        "ok": "#4ade80", "ok_bg": "#13291d", "research": "#fbbf24", "research_bg": "#2e2410",
        "demo": "#c4b5fd", "demo_bg": "#251d3b", "nodata": "#a3abb7", "nodata_bg": "#232931",
        "concept": "#93c5fd", "concept_bg": "#16233a", "danger": "#f87171", "danger_bg": "#3a1a1a",
        "warn": "#fbbf24", "warn_bg": "#2e2410", "grid": "#262d36",
        "series": ["#7aa7ff", "#f59e0b", "#34d399", "#a78bfa", "#fb7185", "#22d3ee", "#a3e635", "#d6d3d1"],
    },
}
STATUS_STYLE = {  # status -> palette keys (text, background), short label
    "проверено": ("ok", "ok_bg"), "исследовательское": ("research", "research_bg"),
    "демо": ("demo", "demo_bg"), "нет данных": ("nodata", "nodata_bg"), "концепция": ("concept", "concept_bg"),
}


def mode() -> str:
    try:
        import streamlit as st

        t = st.context.theme.type
        return t if t in PALETTES else "light"
    except Exception:
        return "light"


def palette() -> dict:
    return PALETTES[mode()]


def css() -> str:
    p = palette()
    variables = ";".join(f"--ef-{k.replace('_', '-')}:{v}" for k, v in p.items() if isinstance(v, str))
    return f"""<style>
:root, .stApp {{{variables}}}
.block-container {{ padding-top: 2.2rem; max-width: 1280px; }}
h1, h2, h3 {{ letter-spacing: -0.01em; }}
.ef-header h1 {{ font-size: 1.65rem; margin: 0; color: var(--ef-text); }}
.ef-header .ef-sub {{ color: var(--ef-muted); font-size: 0.92rem; margin-top: 4px; }}
.ef-header {{ margin-bottom: 18px; }}
.ef-card {{ background: var(--ef-surface); border: 1px solid var(--ef-border); border-radius: 10px;
           padding: 16px 18px; height: 100%; }}
.ef-kpi-label {{ font-size: 0.82rem; color: var(--ef-muted); font-weight: 600; }}
.ef-kpi-value {{ font-size: 1.85rem; font-weight: 700; color: var(--ef-text); line-height: 1.2; margin: 6px 0 4px;
                font-variant-numeric: tabular-nums; overflow-wrap: anywhere; }}
.ef-kpi-hint {{ font-size: 0.8rem; color: var(--ef-muted); line-height: 1.45; }}
.ef-badge {{ display: inline-block; font-size: 0.72rem; font-weight: 700; padding: 2px 8px; border-radius: 999px;
            letter-spacing: 0.02em; white-space: nowrap; vertical-align: middle; }}
.ef-caveat {{ border-left: 3px solid var(--ef-warn); background: var(--ef-warn-bg); color: var(--ef-text);
             padding: 10px 14px; border-radius: 6px; font-size: 0.86rem; line-height: 1.5; margin: 8px 0 14px; }}
.ef-banner {{ border: 1px solid var(--ef-border); border-left: 4px solid var(--ef-primary); background: var(--ef-surface);
             color: var(--ef-text); padding: 10px 14px; border-radius: 6px; font-size: 0.86rem; margin: 0 0 16px; }}
.ef-advice h4 {{ margin: 0 0 8px; font-size: 1.02rem; color: var(--ef-text); }}
.ef-advice p {{ margin: 0 0 8px; font-size: 0.9rem; line-height: 1.55; color: var(--ef-text); }}
.ef-advice .ef-k {{ font-weight: 700; color: var(--ef-text-2); }}
.ef-empty {{ text-align: center; padding: 32px 16px; color: var(--ef-muted); border: 1px dashed var(--ef-border);
            border-radius: 10px; }}
.ef-empty b {{ color: var(--ef-text); display: block; font-size: 1rem; margin-bottom: 6px; }}
.ef-term {{ border-bottom: 1px dotted var(--ef-muted); cursor: help; }}
.ef-light {{ display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 8px; }}
.ef-muted {{ color: var(--ef-muted); }}
.section-title {{ font-size: 1.02rem; font-weight: 700; color: var(--ef-text); margin: 26px 0 12px;
                 padding-bottom: 6px; border-bottom: 1px solid var(--ef-border); }}
.glass-card, .metric-card {{ background: var(--ef-surface); border: 1px solid var(--ef-border); border-radius: 10px;
                            padding: 16px 18px; color: var(--ef-text); }}
.metric-card {{ border-left: 3px solid var(--ef-primary); }}
.metric-card.accent-red {{ border-left-color: var(--ef-danger); }}
.metric-card.accent-amber {{ border-left-color: var(--ef-warn); }}
.metric-card.accent-green {{ border-left-color: var(--ef-ok); }}
.metric-value {{ font-size: 1.85rem; font-weight: 700; color: var(--ef-text); line-height: 1.2; }}
.metric-label {{ font-size: 0.8rem; color: var(--ef-muted); font-weight: 600; margin-top: 4px; }}
.metric-delta {{ font-size: 0.8rem; color: var(--ef-muted); margin-top: 4px; }}
.glass-alert {{ background: var(--ef-surface); border: 1px solid var(--ef-border); border-left: 3px solid var(--ef-muted);
               border-radius: 6px; padding: 10px 14px; margin-bottom: 6px; font-size: 0.88rem; color: var(--ef-text); }}
@media (max-width: 640px) {{
  .block-container {{ padding-left: 1rem; padding-right: 1rem; }}
  .ef-kpi-value {{ font-size: 1.5rem; }}
  .ef-header h1 {{ font-size: 1.35rem; }}
}}
</style>"""


def plotly_template(m: str | None = None) -> go.layout.Template:
    p = PALETTES[m or mode()]
    return go.layout.Template(layout=go.Layout(
        font=dict(family="sans-serif", size=13, color=p["text"]),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", colorway=p["series"],
        title=dict(font=dict(size=15, color=p["text"]), x=0, xanchor="left"),
        xaxis=dict(gridcolor=p["grid"], linecolor=p["border"], zerolinecolor=p["border"], tickfont=dict(color=p["muted"]),
                   title=dict(font=dict(color=p["muted"]))),
        yaxis=dict(gridcolor=p["grid"], linecolor=p["border"], zerolinecolor=p["border"], tickfont=dict(color=p["muted"]),
                   title=dict(font=dict(color=p["muted"]))),
        legend=dict(font=dict(color=p["text_2"]), bgcolor="rgba(0,0,0,0)"),
        hoverlabel=dict(bgcolor=p["surface"], bordercolor=p["border"], font=dict(color=p["text"])),
        margin=dict(l=8, r=8, t=44, b=8), separators=", "))


def apply(fig: go.Figure, title: str | None = None, height: int | None = None) -> go.Figure:
    fig.update_layout(template=plotly_template())
    if title is not None:
        fig.update_layout(title_text=title)
    if height:
        fig.update_layout(height=height)
    return fig


for _m in PALETTES:
    pio.templates[f"eduforecast_{_m}"] = plotly_template(_m)

# ── Russian formatting ──────────────────────────────────────────────────────────────────
NBSP = " "
MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября",
          "ноября", "декабря"]


def num(x, decimals: int = 0) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "—"
    return f"{x:,.{decimals}f}".replace(",", " ").replace(".", ",").replace(" ", NBSP).replace("-", "−")


def pct(x, decimals: int = 1, signed: bool = False) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "—"
    s = num(x * 100, decimals) + "%"
    return ("+" + s) if signed and x > 0 else s


def ru_date(d: date | datetime | str | None, with_time: bool = False) -> str:
    if d is None:
        return "—"
    if isinstance(d, str):
        try:
            d = datetime.fromisoformat(d.replace("Z", "+00:00"))
        except ValueError:
            return d
    out = f"{d.day} {MONTHS[d.month - 1]} {d.year}"
    if with_time and isinstance(d, datetime):
        out += f", {d:%H:%M}"
    return out


# ── WCAG contrast ───────────────────────────────────────────────────────────────────────
def _lum(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    rgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a: str, b: str) -> float:
    la, lb = sorted([_lum(a), _lum(b)], reverse=True)
    return (la + 0.05) / (lb + 0.05)
