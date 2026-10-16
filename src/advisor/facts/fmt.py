"""Russian number formatting for fact values (the only way numbers reach the user)."""
from __future__ import annotations

import math

NBSP = " "  # narrow no-break space as thousands separator


def _num(x: float, decimals: int) -> str:
    s = f"{x:,.{decimals}f}".replace(",", " ").replace(".", ",").replace(" ", NBSP)
    return s.replace("-", "−")


def format_value(value, unit: str) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "нет данных"
    if isinstance(value, bool) or unit == "bool":
        return "да" if value else "нет"
    if isinstance(value, str):
        return value
    v = float(value)
    if unit == "auc":
        return _num(v, 2)
    if unit == "brier":
        return _num(v, 3)
    if unit == "p_value":
        return "< 0,001" if v < 0.001 else _num(v, 3)
    if unit == "share":
        return _num(v * 100, 1) + "%"
    if unit == "gain":
        sign = "+" if v > 0 else ""
        return sign + _num(v * 100, 1) + "%"
    if unit == "pp":
        sign = "+" if v > 0 else ""
        return sign + _num(v, 2) + " п.п."
    if unit == "count":
        return _num(v, 0)
    if unit == "kzt_thousand":
        return _num(v, 0) + " тыс. тенге"
    if unit == "ratio":
        return _num(v, 2)
    if unit == "log":
        return _num(v, 4)
    return _num(v, 2)
