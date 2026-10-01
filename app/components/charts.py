import plotly.graph_objects as go
import pandas as pd
import numpy as np

C_VIOLET  = "#2563eb"
C_INDIGO  = "#64748b"
C_BLUE    = "#94a3b8"
C_DARK    = "#0f172a"
C_MUTED   = "#6b7280"
RISK_COLORS = {"HIGH": "#dc2626", "MEDIUM": "#d97706", "LOW": "#059669"}

TRANSPARENT = "rgba(0,0,0,0)"
GRID_COLOR  = "#eef0f3"
LINE_COLOR  = "#e3e6eb"

FONT_STACK = "-apple-system, Helvetica, Arial, sans-serif"

def _base(fig: go.Figure, title: str = "", height: int = 350) -> go.Figure:
    fig.update_layout(
        title=dict(
            text=title,
            font=dict(size=13, color=C_DARK, family=FONT_STACK),
            x=0, xanchor="left",
        ),
        height=height,
        plot_bgcolor=TRANSPARENT,
        paper_bgcolor=TRANSPARENT,
        font=dict(family=FONT_STACK, color=C_DARK, size=12),
        margin=dict(l=8, r=8, t=40, b=8),
        legend=dict(
            bgcolor="rgba(255,255,255,0)",
            bordercolor=LINE_COLOR,
            borderwidth=0,
            font=dict(size=11),
        ),
        hoverlabel=dict(
            bgcolor="#ffffff",
            bordercolor=LINE_COLOR,
            font=dict(color=C_DARK, family=FONT_STACK, size=12),
        ),
    )
    fig.update_xaxes(
        showgrid=True, gridcolor=GRID_COLOR, gridwidth=1,
        linecolor=LINE_COLOR, zerolinecolor=LINE_COLOR,
        tickfont=dict(color=C_MUTED, size=11),
    )
    fig.update_yaxes(
        showgrid=True, gridcolor=GRID_COLOR, gridwidth=1,
        linecolor=LINE_COLOR, zerolinecolor=GRID_COLOR,
        tickfont=dict(color=C_MUTED, size=11),
    )
    return fig

def activity_line_chart(weekly_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=weekly_df["week"], y=weekly_df["total_clicks"],
        mode="lines", name="Клики",
        line=dict(color=C_VIOLET, width=2),
        fill="tozeroy",
        fillcolor="rgba(37,99,235,0.06)",
        hovertemplate="Неделя %{x}: %{y:,.0f} кликов<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=weekly_df["week"], y=weekly_df["active_students"],
        mode="lines", name="Активных студентов",
        line=dict(color=C_BLUE, width=1.5, dash="dot"),
        yaxis="y2",
        hovertemplate="Неделя %{x}: %{y} студентов<extra></extra>",
    ))
    fig.update_layout(
        yaxis=dict(title=dict(text="Кликов", font=dict(color=C_VIOLET, size=11))),
        yaxis2=dict(
            overlaying="y", side="right",
            title=dict(text="Студентов", font=dict(color=C_BLUE, size=11)),
            tickfont=dict(color=C_BLUE, size=11),
            showgrid=False,
            linecolor=LINE_COLOR,
        ),
        xaxis=dict(title="Неделя курса"),
        legend=dict(orientation="h", y=-0.22, x=0.5, xanchor="center"),
    )
    return _base(fig, "Активность студентов по неделям", 340)

def risk_donut_chart(risk_counts: dict) -> go.Figure:
    labels = ["Высокий", "Средний", "Низкий"]
    values = [risk_counts.get("HIGH", 0), risk_counts.get("MEDIUM", 0), risk_counts.get("LOW", 0)]
    colors = [RISK_COLORS["HIGH"], RISK_COLORS["MEDIUM"], RISK_COLORS["LOW"]]
    total  = sum(values)

    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=0.6,
        marker=dict(
            colors=colors,
            line=dict(color="#ffffff", width=2),
        ),
        textinfo="percent",
        textfont=dict(size=12, color="#fff"),
        hovertemplate="%{label}: %{value} студентов (%{percent})<extra></extra>",
    ))
    fig.update_layout(
        showlegend=True,
        legend=dict(orientation="h", y=-0.12, x=0.5, xanchor="center"),
        annotations=[dict(
            text=f"<b>{total}</b><br><span style='font-size:10px;'>студентов</span>",
            x=0.5, y=0.5, font=dict(size=14, color=C_DARK), showarrow=False,
        )],
    )
    return _base(fig, "Распределение риска", 300)

def faculty_comparison_chart(summary_df: pd.DataFrame) -> go.Figure:
    df = summary_df.sort_values("health_index", ascending=True)
    colors = [
        "#ef4444" if h < 40 else "#f59e0b" if h < 60 else C_INDIGO if h < 80 else "#10b981"
        for h in df["health_index"]
    ]
    short_names = df["faculty"].str.replace("Факультет ", "", regex=False)

    fig = go.Figure(go.Bar(
        y=short_names, x=df["health_index"],
        orientation="h",
        marker=dict(color=colors),
        text=[f"{v:.0f}" for v in df["health_index"]],
        textposition="outside",
        textfont=dict(color=C_DARK, size=12, family=FONT_STACK),
        hovertemplate="%{y}: %{x:.1f}/100<extra></extra>",
    ))
    fig.add_vline(x=60, line=dict(dash="dash", color=C_MUTED, width=1.5),
                  annotation=dict(text="Норма 60", font=dict(color=C_MUTED, size=11)))
    fig.update_xaxes(range=[0, 108], title="Индекс здоровья (0–100)")
    return _base(fig, "Индекс здоровья факультетов", 380)

def withdrawal_comparison_chart(summary_df: pd.DataFrame) -> go.Figure:
    df = summary_df.sort_values("withdrawal_rate", ascending=False)
    short_names = df["faculty"].str.replace("Факультет ", "", regex=False)
    colors = [
        "#ef4444" if r > 30 else "#f59e0b" if r > 20 else "#10b981"
        for r in df["withdrawal_rate"]
    ]

    fig = go.Figure(go.Bar(
        x=short_names, y=df["withdrawal_rate"],
        marker=dict(color=colors),
        text=[f"{v:.1f}%" for v in df["withdrawal_rate"]],
        textposition="outside",
        textfont=dict(color=C_DARK, size=11),
        hovertemplate="%{x}: %{y:.1f}% отчислений<extra></extra>",
    ))
    fig.add_hline(y=25, line=dict(dash="dash", color=C_MUTED, width=1.5),
                  annotation=dict(text="Бенчмарк 25%", font=dict(color=C_MUTED, size=11)))
    fig.update_yaxes(title="% отчислений")
    return _base(fig, "Процент отчислений по факультетам", 360)

def score_histogram(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure(go.Histogram(
        x=df["avg_score"], nbinsx=22,
        marker=dict(color=C_VIOLET, opacity=0.85),
        hovertemplate="Балл %{x:.0f}: %{y} студентов<extra></extra>",
    ))
    avg = df["avg_score"].mean()
    fig.add_vline(x=avg, line=dict(color="#dc2626", width=1.5, dash="dash"),
                  annotation=dict(text=f"Ср. {avg:.1f}",
                                  font=dict(color="#dc2626", size=11),
                                  bgcolor="#ffffff"))
    fig.update_xaxes(title="Средний балл")
    fig.update_yaxes(title="Студентов")
    return _base(fig, "Распределение баллов", 300)

def retention_forecast_chart(weeks_hist, survived_pct, forecast_weeks, forecast_pct) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=weeks_hist, y=survived_pct,
        mode="lines", name="Факт",
        line=dict(color=C_VIOLET, width=2),
        fill="tozeroy",
        fillcolor="rgba(37,99,235,0.06)",
        hovertemplate="Неделя %{x}: %{y:.1f}% студентов<extra></extra>",
    ))
    if forecast_weeks:
        xc = [weeks_hist[-1]] + forecast_weeks
        yc = [survived_pct[-1]] + forecast_pct
        fig.add_trace(go.Scatter(
            x=xc, y=yc,
            mode="lines", name="Прогноз",
            line=dict(color="#d97706", width=2, dash="dash"),
            hovertemplate="Прогноз нед. %{x}: %{y:.1f}%<extra></extra>",
        ))
    fig.add_hline(y=75, line=dict(color="#dc2626", width=1.5, dash="dot"),
                  annotation=dict(text="Цель 75%",
                                  font=dict(color="#dc2626", size=11),
                                  bgcolor="#ffffff"))
    fig.update_xaxes(title="Неделя курса")
    fig.update_yaxes(title="% удержанных студентов", range=[0, 108])
    return _base(fig, "Прогноз удержания студентов (Retention Rate)", 360)

def worldbank_chart(wb_df: pd.DataFrame, indicator_name: str) -> go.Figure:
    df = wb_df.dropna(subset=["value"]).sort_values("year")
    fig = go.Figure(go.Scatter(
        x=df["year"], y=df["value"],
        mode="lines+markers",
        line=dict(color=C_VIOLET, width=2),
        marker=dict(size=6, color=C_VIOLET,
                    line=dict(color="#ffffff", width=1.5)),
        fill="tozeroy",
        fillcolor="rgba(37,99,235,0.06)",
        hovertemplate="%{x}: %{y:.1f}%<extra></extra>",
    ))
    fig.update_xaxes(title="Год", tickformat="d")
    fig.update_yaxes(title="%")
    return _base(fig, indicator_name, 300)

def shap_bar_chart(feature_cols: list, mean_shap: np.ndarray) -> go.Figure:
    labels = {
        "total_clicks": "Активность в LMS",
        "active_days": "Активные дни",
        "assessments_submitted": "Сданные задания",
        "avg_score": "Средний балл",
        "min_score": "Минимальный балл",
        "num_of_prev_attempts": "Повторные попытки",
        "studied_credits": "Учебная нагрузка",
        "unregistered": "Статус регистрации",
        "edu_enc": "Уровень образования",
        "imd_enc": "Соц-эконом. фактор",
        "age_enc": "Возраст",
    }
    n = 8
    idx = np.argsort(mean_shap)[::-1][:n]
    ys = [labels.get(feature_cols[i], feature_cols[i]) for i in idx][::-1]
    xs = [float(mean_shap[i]) for i in idx][::-1]

    bar_colors = [
        f"rgba(37,99,235,{0.45 + 0.50 * (v / max(xs))})" for v in xs
    ]

    fig = go.Figure(go.Bar(
        y=ys, x=xs, orientation="h",
        marker=dict(color=bar_colors),
        hovertemplate="%{y}: %{x:.4f}<extra></extra>",
    ))
    fig.update_xaxes(title="Средний |SHAP| (влияние на риск)")
    return _base(fig, "Топ-факторы риска (SHAP-анализ)", 320)
