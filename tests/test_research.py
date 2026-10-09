import pandas as pd
import pytest

from src.research.aggregate import build_yearly_counts, filter_training_window, partial_years
from src.research.baseline import smape
from src.research.config import PARTIAL_YEAR, TRAINING_YEAR_MAX, TRAINING_YEAR_MIN
from src.research.forecast import backtest_leave_last_year_out


@pytest.fixture(scope="module")
def counts():
    return build_yearly_counts()


def test_snapshot_marks_partial_year(counts):
    assert counts.loc[counts["year"] == PARTIAL_YEAR, "is_partial"].all()
    assert not counts.loc[counts["year"] < PARTIAL_YEAR, "is_partial"].any()


def test_training_window_uses_complete_years_only(counts):
    training = filter_training_window(counts)
    assert training["year"].min() == TRAINING_YEAR_MIN
    assert training["year"].max() == TRAINING_YEAR_MAX
    assert not training["is_partial"].any()
    assert list(partial_years(counts)["year"]) == [PARTIAL_YEAR]


def test_backtest_predicts_last_complete_year(counts):
    result = backtest_leave_last_year_out(filter_training_window(counts))
    assert result.backtest_year == TRAINING_YEAR_MAX
    assert result.actual == 606
    assert set(result.predictions) == {"linear", "logistic"}


def test_backtest_rejects_partial_years(counts):
    with pytest.raises(ValueError):
        backtest_leave_last_year_out(counts[counts["year"] >= TRAINING_YEAR_MIN])


def test_smape_basic_properties():
    assert smape([100, 200], [100, 200]) == 0
    assert smape([0, 0], [0, 0]) == 0
    assert smape([100], [50]) == pytest.approx(smape([50], [100]))
    assert smape(pd.Series([10.0]), pd.Series([0.0])) == pytest.approx(200)
