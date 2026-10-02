from dataclasses import dataclass, field

import pandas as pd
from prophet import Prophet

from src.research.aggregate import to_prophet_frame
from src.research.config import LOGISTIC_CAP_MULTIPLIER

FORECAST_YEARS_AHEAD = 3


def _new_model(growth: str) -> Prophet:
    return Prophet(
        growth=growth,
        yearly_seasonality=False,
        weekly_seasonality=False,
        daily_seasonality=False,
        interval_width=0.80,
    )


def compute_logistic_cap(df_yearly: pd.DataFrame, multiplier: float = LOGISTIC_CAP_MULTIPLIER) -> float:
    return float(df_yearly["works_count"].max()) * multiplier


def fit_linear(df_prophet: pd.DataFrame) -> Prophet:
    model = _new_model("linear")
    model.fit(df_prophet)
    return model


def fit_logistic(df_prophet: pd.DataFrame, cap: float) -> Prophet:
    df_capped = df_prophet.copy()
    df_capped["cap"] = cap
    model = _new_model("logistic")
    model.fit(df_capped)
    return model


def make_future(model: Prophet, periods: int, cap: float | None = None) -> pd.DataFrame:
    future = model.make_future_dataframe(periods=periods, freq="YS")
    if cap is not None:
        future["cap"] = cap
    return future


def predict(model: Prophet, periods: int, cap: float | None = None) -> pd.DataFrame:
    future = make_future(model, periods, cap)
    return model.predict(future)


@dataclass
class BacktestResult:
    backtest_year: int
    actual: float
    predictions: dict = field(default_factory=dict)
    note: str = (
        "Leave-last-year-out sanity check on a single held-out point. "
        "NOT k-fold or time-series cross-validation: with only 6-7 yearly "
        "observations there isn't enough data for a statistically meaningful CV."
    )


def backtest_leave_last_year_out(
    df_yearly: pd.DataFrame,
    cap_multiplier: float = LOGISTIC_CAP_MULTIPLIER,
) -> BacktestResult:
    last_year = int(df_yearly["year"].max())
    train_df = df_yearly[df_yearly["year"] < last_year].reset_index(drop=True)
    actual = float(df_yearly.loc[df_yearly["year"] == last_year, "works_count"].iloc[0])

    train_prophet = to_prophet_frame(train_df)
    cap = compute_logistic_cap(train_df, cap_multiplier)

    predictions = {}
    for growth in ("linear", "logistic"):
        if growth == "logistic":
            model = fit_logistic(train_prophet, cap)
            fcst = predict(model, periods=1, cap=cap)
        else:
            model = fit_linear(train_prophet)
            fcst = predict(model, periods=1)

        row = fcst.iloc[-1]
        predicted = float(row["yhat"])
        abs_error = abs(predicted - actual)
        predictions[growth] = {
            "predicted": predicted,
            "lower": float(row["yhat_lower"]),
            "upper": float(row["yhat_upper"]),
            "abs_error": abs_error,
            "pct_error": abs_error / actual * 100 if actual else float("nan"),
        }

    return BacktestResult(backtest_year=last_year, actual=actual, predictions=predictions)


@dataclass
class ForecastComparison:
    history: pd.DataFrame
    linear_forecast: pd.DataFrame
    logistic_forecast: pd.DataFrame
    logistic_cap: float
    backtest: BacktestResult


def run_forecast_comparison(
    df_yearly: pd.DataFrame,
    years_ahead: int = FORECAST_YEARS_AHEAD,
) -> ForecastComparison:
    df_prophet = to_prophet_frame(df_yearly)
    cap = compute_logistic_cap(df_yearly)

    linear_model = fit_linear(df_prophet)
    linear_fcst = predict(linear_model, periods=years_ahead)

    logistic_model = fit_logistic(df_prophet, cap)
    logistic_fcst = predict(logistic_model, periods=years_ahead, cap=cap)

    backtest = backtest_leave_last_year_out(df_yearly)

    return ForecastComparison(
        history=df_yearly,
        linear_forecast=linear_fcst,
        logistic_forecast=logistic_fcst,
        logistic_cap=cap,
        backtest=backtest,
    )
