"""Fact registry: schema, sources, values equal to the saved result files."""
import subprocess

import pytest

from src.advisor.facts.fmt import format_value
from src.advisor.facts.registry import Registry, build
from src.advisor.facts.schema import STATUSES, validate_all
from src.config import BASE_DIR


@pytest.fixture(scope="module")
def reg():
    return Registry.load()


def test_snapshot_schema(reg):
    facts = list(reg.facts.values())
    assert len(facts) > 300
    assert validate_all(facts) == []
    for f in facts:
        assert f["source"] and f["caveat"] and f["status"] in STATUSES


def test_sources_exist_or_are_untracked_results(reg):
    tracked = set(subprocess.run(["git", "ls-files"], cwd=BASE_DIR, capture_output=True, text=True).stdout.split())
    sources = {f["source"] for f in reg.facts.values()}
    missing = [s for s in sources if not (BASE_DIR / s).exists()]
    assert not [s for s in missing if s in tracked], "tracked source files are missing"
    if missing:
        pytest.skip(f"local result files not in this checkout (gitignored): {sorted(missing)[:3]}")


def test_values_match_source_files(reg):
    rebuilt = {f.id: f for f in build()}
    checked = 0
    for fid, f in rebuilt.items():
        if f.status == "нет данных" and not (BASE_DIR / f.source).exists():
            continue  # this checkout has no such file; the snapshot keeps the saved value
        snap = reg.get(fid)
        assert snap is not None, fid
        assert snap["status"] == f.status, fid
        if isinstance(f.value, float):
            assert snap["value"] == pytest.approx(f.value, rel=1e-9, abs=1e-12), fid
        else:
            assert snap["value"] == f.value, fid
        checked += 1
    assert checked > 100


def test_no_student_level_facts(reg):
    for f in reg.facts.values():
        assert "id_student" not in f["id"] and "student_" not in f["id"]
        if "riskgroup" in f["id"] and f["id"].endswith("high_size") and f["value"] is not None:
            assert f["value"] >= 30


def test_unimplemented_modules_have_no_numbers(reg):
    for key in ("international", "upbringing"):
        assert reg.get(f"system.module.{key}.status")["value"] == "нет данных"
        for f in reg.select(module=key):
            assert f["status"] == "нет данных"


def test_russian_formatting():
    assert format_value(0.7031, "auc") == "0,70"
    assert format_value(0.1004, "gain") == "+10,0%"
    assert format_value(-233144, "kzt_thousand") == "−233 144 тыс. тенге"
    assert format_value(None, "share") == "нет данных"
    assert format_value(True, "bool") == "да"
