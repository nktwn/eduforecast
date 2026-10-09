import numpy as np
import plotly.graph_objects as go

from components.charts import C_BLUE, C_DARK, C_MUTED, C_VIOLET, _base

C_PEER = "#94a3b8"
C_NAIVE = "#64748b"
C_GROUP = "#d97706"
C_COVID = "rgba(217, 119, 6, 0.08)"
C_WARN = "#d97706"
C_CRIT = "#dc2626"

POINT_FLAG_STYLE = {
    "ID_TRANSITION": ("Смена UNITID / отчётности", C_CRIT, "x"),
    "MERGER_ABSORPTION": ("Поглощение другого вуза", C_CRIT, "x"),
    "OUTLIER_CHANGE": ("Аномальное изменение", C_WARN, "diamond-open"),
    "SMALL_COHORT": ("Когорта < 30", C_WARN, "circle-open"),
    "GASB75_2018": ("GASB 75 (2018)", C_MUTED, "triangle-up-open"),
    "FINANCE_PARTIAL": ("Частичная финотчётность", C_WARN, "square-open"),
}


def fmt_value(value, unit: str) -> str:
    if value is None:
        return "—"
    if unit == "%":
        return f"{value:.1f}%"
    if unit.startswith("$"):
        return f"${value:,.0f}"
    return f"{value:,.0f}"


def change_text(change: float, scale: str) -> str:
    if scale == "log_ratio":
        return f"{(np.exp(change) - 1) * 100:+.1f}%"
    return f"{change:+.1f} п.п."


def history_chart(block: dict, title: str, forecast_label: str = "Прогноз модели") -> go.Figure:
    unit = block["unit"]
    hist = block["history"]
    years = [p["year"] for p in hist]
    values = [p["value"] for p in hist]
    fig = go.Figure()

    covid = sorted({p["year"] for p in hist if "COVID_YEAR" in p["flags"]})
    if covid:
        fig.add_vrect(x0=min(covid) - 0.5, x1=max(covid) + 0.5, fillcolor=C_COVID, line_width=0, layer="below",
                      annotation=dict(text="COVID", font=dict(size=10, color=C_WARN), yanchor="top"),
                      annotation_position="top left")

    peer = block["peer_median_history"]
    if peer:
        fig.add_trace(go.Scatter(x=[p["year"] for p in peer], y=[p["value"] for p in peer], mode="lines",
                                 name="Медиана похожих вузов", line=dict(color=C_PEER, width=1.5, dash="dot"),
                                 hovertemplate="Похожие вузы, %{x}: %{y:,.1f}<extra></extra>"))

    fig.add_trace(go.Scatter(x=years, y=values, mode="lines+markers", name="Факт", connectgaps=False,
                             line=dict(color=C_DARK, width=2), marker=dict(size=6, color=C_DARK),
                             hovertemplate="%{x}: %{y:,.1f}<extra></extra>"))

    for code, (label, color, symbol) in POINT_FLAG_STYLE.items():
        pts = [(p["year"], p["value"]) for p in hist if code in p["flags"] and p["value"] is not None]
        if pts:
            fig.add_trace(go.Scatter(x=[x for x, _ in pts], y=[y for _, y in pts], mode="markers", name=label,
                                     marker=dict(size=14, color=color, symbol=symbol, line=dict(width=2, color=color)),
                                     hovertemplate=f"{label}, %{{x}}<extra></extra>"))
    for p in hist:
        if "ID_TRANSITION" in p["flags"] or "MERGER_ABSORPTION" in p["flags"]:
            fig.add_vline(x=p["year"] - 0.5, line=dict(color=C_CRIT, width=1, dash="dash"))

    fc = block["forecast"]
    if fc:
        last = next((p for p in reversed(hist) if p["value"] is not None), None)
        iv = fc["interval"]
        fig.add_trace(go.Scatter(x=[fc["year"], fc["year"]], y=[iv["lower"], iv["upper"]], mode="lines",
                                 name=f"Интервал {int(iv['level'] * 100)}%",
                                 line=dict(color="rgba(37, 99, 235, 0.35)", width=10),
                                 hovertemplate="Интервал: %{y:,.1f}<extra></extra>"))
        if last:
            fig.add_trace(go.Scatter(x=[last["year"], fc["year"]], y=[last["value"], fc["value"]], mode="lines",
                                     showlegend=False, line=dict(color=C_VIOLET, width=2, dash="dash"),
                                     hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=[fc["year"]], y=[fc["value"]], mode="markers", name=forecast_label,
                                 marker=dict(size=11, color=C_VIOLET, line=dict(width=2, color="#ffffff")),
                                 hovertemplate=f"Прогноз {fc['year']}: %{{y:,.1f}}<extra></extra>"))
        for b, (name, color, symbol) in zip(block["baselines"], [("Naive", C_NAIVE, "line-ew-open"),
                                                                ("Средний рост группы", C_GROUP, "line-ew-open")]):
            if b["value"] is not None:
                fig.add_trace(go.Scatter(x=[fc["year"] + 0.18], y=[b["value"]], mode="markers", name=name,
                                         marker=dict(size=16, color=color, symbol=symbol, line=dict(width=3, color=color)),
                                         hovertemplate=f"{name}: %{{y:,.1f}}<extra></extra>"))

    fig.update_xaxes(dtick=2, range=[min(years) - 0.6, (fc["year"] if fc else max(years)) + 0.8])
    fig.update_yaxes(title=dict(text=unit, font=dict(size=11, color=C_MUTED)))
    fig.update_layout(legend=dict(orientation="h", y=-0.18, x=0, font=dict(size=10.5)), hovermode="closest")
    return _base(fig, title, 400)


def shap_waterfall(explanation: dict, top: int = 8) -> go.Figure:
    scale = explanation["scale"]
    mult = 100.0 if scale == "log_ratio" else 1.0
    unit = "п.п. логарифмического роста ×100 (≈ %)" if scale == "log_ratio" else "п.п."
    contribs = sorted(explanation["contributions"], key=lambda c: abs(c["contribution"]), reverse=True)
    head, tail = contribs[:top], contribs[top:]

    def label(c):
        v = c["feature_value"]
        if v is None:
            return c["label"]
        return f"{c['label']} = {v:,.3g}"

    names = ["Среднее по выборке"] + [label(c) for c in reversed(head)]
    measures = ["absolute"] + ["relative"] * len(head)
    values = [explanation["base_value"] * mult] + [c["contribution"] * mult for c in reversed(head)]
    if tail:
        names.insert(1, f"Остальные {len(tail)} признаков")
        measures.insert(1, "relative")
        values.insert(1, sum(c["contribution"] for c in tail) * mult)
    names.append("Прогноз изменения")
    measures.append("total")
    values.append(explanation["prediction"] * mult)

    fig = go.Figure(go.Waterfall(
        orientation="h", y=names, x=values, measure=measures,
        increasing=dict(marker=dict(color="#059669")), decreasing=dict(marker=dict(color=C_CRIT)),
        totals=dict(marker=dict(color=C_VIOLET)), connector=dict(line=dict(color="#e3e6eb", width=1)),
        text=[f"{v:+.2f}" for v in values], textposition="outside", textfont=dict(size=10.5, color=C_DARK),
        hovertemplate="%{y}: %{x:+.3f}<extra></extra>",
    ))
    running = np.cumsum([values[0]] + values[1:-1])
    lo, hi = min(0.0, running.min(), values[-1]), max(0.0, running.max(), values[-1])
    pad = (hi - lo) * 0.18 or 1.0
    fig.update_xaxes(title=dict(text=unit, font=dict(size=11, color=C_MUTED)), range=[lo - pad, hi + pad])
    fig.update_yaxes(automargin=True, tickfont=dict(size=11, color=C_DARK))
    return _base(fig, "", 60 + 34 * len(names))


def peer_bar(values: list[tuple[str, float | None, bool]], unit: str, title: str) -> go.Figure:
    rows = [(n, v, me) for n, v, me in values if v is not None]
    rows.sort(key=lambda r: r[1])
    fig = go.Figure(go.Bar(
        x=[v for _, v, _ in rows], y=[n for n, _, _ in rows], orientation="h",
        marker=dict(color=[C_VIOLET if me else C_BLUE for _, _, me in rows]),
        text=[fmt_value(v, unit) for _, v, _ in rows], textposition="outside",
        textfont=dict(size=11, color=C_DARK), hovertemplate="%{y}: %{x:,.1f}<extra></extra>",
    ))
    fig.update_yaxes(automargin=True)
    top = max((v for _, v, _ in rows), default=1)
    fig.update_xaxes(title=dict(text=unit, font=dict(size=11, color=C_MUTED)), range=[0, top * 1.22])
    return _base(fig, title, 80 + 38 * len(rows))
