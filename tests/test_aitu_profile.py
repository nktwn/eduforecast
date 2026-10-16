"""AITU profile (data/aitu): sum checks and structural ratios."""
import pytest

from src.finance.aitu_profile import CHECK_TOLERANCE, load, structure, sum_checks


@pytest.fixture(scope="module")
def df():
    return load()


def test_all_values_unverified_and_two_years(df):
    assert set(df["year"]) == {2019, 2020}
    assert not df["verified"].any()
    assert df["page"].notna().all()


def test_sum_checks_within_tolerance(df):
    checks = sum_checks(df)
    expected = {"revenue_by_source", "services_by_item", "expenses_by_item",
                "assets_equal_liabilities_and_equity", "revenue_minus_expenses_equals_operating_loss"}
    assert expected <= set(checks.loc[checks["year"] == 2020, "check"])
    bad = checks[checks["difference"].abs() > CHECK_TOLERANCE]
    assert bad.empty, bad.to_string()


def test_structure_values(df):
    s = structure(df).loc[2020]
    assert s["share_state_order_in_revenue"] == pytest.approx(998977 / 1281266)
    assert s["share_payroll_with_social_in_expenses"] == pytest.approx((849098 + 26741) / 1883010)
    assert s["current_ratio"] == pytest.approx(764668 / 812392)
    assert s["liabilities_to_assets"] == pytest.approx((812392 + 4758933) / 5338181)
    assert s["revenue_per_employee_thousand_kzt"] == pytest.approx(1281266 / 147)
