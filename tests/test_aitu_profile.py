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


def test_rules_have_sources_and_no_invented_thresholds(tmp_path):
    from src.finance.rules import load_rules

    cfg = load_rules()
    for r in cfg["rules"]:
        assert r["source"]["type"] in {"law", "university_document", "supervisor", "us_peer_percentile"}
        if r["source"]["type"] == "supervisor":
            assert r["source"]["status"] == "уточнить"
        if r["source"]["type"] == "us_peer_percentile":
            assert r["source"]["status"] == "ориентир США, контекст другой"
    bad = tmp_path / "rules.yaml"
    bad.write_text("us_peer_group: {}\nrules:\n  - {id: x, label: x, metric: m, op: '<', threshold: 1}\n",
                   encoding="utf-8")
    with pytest.raises(ValueError):
        load_rules(bad)


def test_rules_on_profile_without_us_data(df):
    from src.finance.rules import evaluate

    res = evaluate(structure(df), panel=None).set_index(["rule", "year"])
    assert res.at[("current_ratio_below_one", 2020), "triggered"] is True
    assert res.at[("negative_equity", 2020), "triggered"] is True
    assert res.at[("library_acquisitions_share", 2020), "triggered"] is None
    assert res.at[("compensation_share_vs_us_peers", 2020), "triggered"] is None
