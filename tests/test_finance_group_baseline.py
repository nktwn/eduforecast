import numpy as np
import pandas as pd
import pytest

from src.finance.api.demo_model import META_PATH

from src.finance.api.providers import DemoProvider
from src.finance.baseline import latest_group_changes, predictions
from src.finance.config import PANEL_PATH, YEAR_MAX
from src.finance.criterion import TARGETS

pytestmark = pytest.mark.skipif(not (PANEL_PATH.exists() and META_PATH.exists()),
                                reason="needs local Finance panel and demo models (see README)")


def test_predictions_use_shared_group_changes():
    panel = pd.read_parquet(PANEL_PATH)
    for target in TARGETS:
        groups = latest_group_changes(panel, target)
        p = predictions(panel, target)
        p = p[p["year"] == YEAR_MAX]
        expected = [groups[(g, YEAR_MAX - 1)] for g in p["peer_group"]]
        assert np.allclose(p["pred_group"] - p["z_prev"], expected), target


def test_page_baseline_matches_baseline_module():
    provider = DemoProvider()
    panel = provider.repo.panel
    rng = np.random.default_rng(0)
    ids = [h["series_id"] for h in provider.search("", limit=5000)]
    checked = 0
    for sid in rng.choice(ids, 60, replace=False):
        response = provider.forecast(int(sid))
        group = response["institution"]["peer_group"]
        for block in response["targets"]:
            if not block["forecast"]:
                continue
            target = block["target"]
            naive = next(b["value"] for b in block["baselines"] if b["name"] == "naive")
            page = next(b["value"] for b in block["baselines"] if b["name"] == "peer_group_mean_growth")
            change = latest_group_changes(panel, target).get((group, YEAR_MAX))
            if change is None or page is None:
                continue
            kind = TARGETS[target]["kind"]
            expected = naive * np.exp(change) if kind == "log" else min(100.0, max(0.0, naive + change))
            assert np.isclose(page, expected), (sid, target, page, expected)
            checked += 1
    assert checked > 100


if __name__ == "__main__":
    test_predictions_use_shared_group_changes()
    test_page_baseline_matches_baseline_module()
    print("ok")
