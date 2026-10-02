import pandas as pd
import plotly.graph_objects as go

from components.charts import C_BLUE, C_DARK, C_MUTED, C_VIOLET, _base

C_LOGISTIC = "#059669"


def forecast_comparison_chart(
    history: pd.DataFrame,
    linear_forecast: pd.DataFrame,
    logistic_forecast: pd.DataFrame,
    logistic_cap: float,
) -> go.Figure:
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=history["year"], y=history["works_count"],
        mode="markers+lines", name="Факт",
        line=dict(color=C_DARK, width=2),
        marker=dict(size=7, color=C_DARK),
        hovertemplate="%{x}: %{y:.0f} публикаций<extra></extra>",
    ))

    last_hist_year = int(history["year"].max())

    for fcst, label, color in (
        (linear_forecast, "Прогноз (linear)", C_VIOLET),
        (logistic_forecast, "Прогноз (logistic)", C_LOGISTIC),
    ):
        future = fcst[fcst["ds"].dt.year > last_hist_year].copy()
        future["year"] = future["ds"].dt.year

        fig.add_trace(go.Scatter(
            x=future["year"], y=future["yhat"],
            mode="lines+markers", name=label,
            line=dict(color=color, width=2, dash="dash"),
            marker=dict(size=6, color=color),
            hovertemplate=f"{label} %{{x}}: %{{y:.0f}}<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=pd.concat([future["year"], future["year"][::-1]]),
            y=pd.concat([future["yhat_upper"], future["yhat_lower"][::-1]]),
            fill="toself",
            fillcolor=_hex_to_rgba(color, 0.10),
            line=dict(width=0),
            showlegend=False,
            hoverinfo="skip",
        ))

    fig.add_hline(
        y=logistic_cap, line=dict(color=C_MUTED, width=1, dash="dot"),
        annotation=dict(
            text=f"Потолок логистической модели (экспертная оценка): {logistic_cap:.0f}",
            font=dict(color=C_MUTED, size=10),
        ),
    )

    fig.update_xaxes(title="Год", tickformat="d")
    fig.update_yaxes(title="Публикаций в год")
    fig.update_layout(legend=dict(orientation="h", y=-0.2, x=0.5, xanchor="center"))
    return _base(fig, "Прогноз научной продуктивности: linear vs logistic growth", 420)


def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"
