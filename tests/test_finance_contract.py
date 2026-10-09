import copy

import pytest

from src.finance.api.contract import CONTRACT_VERSION, FLAGS, flag, validate
from src.finance.api.providers import ALIASES, MockProvider
from src.finance.config import finance_name, files_for_year
from src.finance.panel import carnegie_group, name_similarity


@pytest.fixture(scope="module")
def mock_response():
    provider = MockProvider()
    hit = provider.search("mock")[0]
    return provider.forecast(hit["series_id"])


def test_mock_response_matches_contract(mock_response):
    assert validate(mock_response) == []
    assert mock_response["contract_version"] == CONTRACT_VERSION
    assert mock_response["provider"]["is_mock"] is True
    assert any(f["code"] == "MOCK_DATA" for f in mock_response["data_quality"]["flags"])


def test_mock_shap_contributions_sum_to_prediction(mock_response):
    for target in mock_response["targets"]:
        ex = target["explanation"]
        total = ex["base_value"] + sum(c["contribution"] for c in ex["contributions"])
        assert total == pytest.approx(ex["prediction"], abs=1e-9)


def test_mock_interval_contains_forecast(mock_response):
    for target in mock_response["targets"]:
        fc = target["forecast"]
        assert fc["interval"]["lower"] <= fc["value"] <= fc["interval"]["upper"]


def test_schema_rejects_unknown_fields_and_flags(mock_response):
    bad = copy.deepcopy(mock_response)
    bad["unexpected"] = 1
    assert validate(bad)
    bad = copy.deepcopy(mock_response)
    bad["data_quality"]["flags"].append({"code": "NOT_A_FLAG", "severity": "info", "message": "x"})
    assert validate(bad)


def test_flag_catalog():
    for code in FLAGS:
        f = flag(code, year=2020)
        assert f["code"] == code and f["severity"] in {"info", "warning", "critical"}


def test_aliases_map_to_distinct_lowercase_keys():
    assert all(k == k.lower() for k in ALIASES)
    assert len(ALIASES) >= 20


def test_ipeds_file_names():
    assert finance_name(2023, "F1A") == "F2223_F1A"
    assert finance_name(2010, "F2") == "F0910_F2"
    files = files_for_year(2015)
    assert files["hd"] == "HD2015" and files["eap"] == "EAP2015" and files["f_gasb"] == "F1415_F1A"


def test_carnegie_groups():
    assert carnegie_group(15) == "R1"
    assert carnegie_group(18) == "Master's L"
    assert carnegie_group(25) == "Special focus"
    assert carnegie_group(-2) == "Unclassified"


def test_name_similarity():
    assert name_similarity("Kennesaw State University", "Kennesaw State University") == 1
    assert name_similarity("Armstrong State University", "Georgia Southern University") < 0.5
