"""Advisor core with a scripted LLM: schema, placeholders, rejected numbers, no data, no key, 20 control questions."""
import json

import pytest

from src.advisor.config import Settings
from src.advisor.control_questions import CONTROL, answer, check_properties, tool_call
from src.advisor.core import Advisor, redact
from src.advisor.facts.registry import Registry
from src.advisor.llm import LLMError, ScriptedProvider
from src.advisor.validate import check, parse, render

KEYED = Settings("test-key-not-real", "https://example.invalid/v1", "stub-model", 5.0, "openai-compatible")
NOKEY = Settings("", "https://example.invalid/v1", "stub-model", 5.0, "openai-compatible")


@pytest.fixture(scope="module")
def reg():
    return Registry.load()


def make(replies, reg, tmp_path, settings=KEYED):
    return Advisor(provider=ScriptedProvider(replies) if replies is not None else None, settings=settings, reg=reg,
                   log_path=tmp_path / "log.jsonl")


@pytest.mark.parametrize("spec", CONTROL, ids=[f"q{c['id']:02d}" for c in CONTROL])
def test_control_question(spec, reg, tmp_path):
    replies = list(spec["stub"])
    if spec.get("tools_unsupported"):
        replies = [LLMError("tools_unsupported")] + replies
    adv = make(None if spec.get("no_key") else replies, reg, tmp_path, NOKEY if spec.get("no_key") else KEYED)
    res = adv.ask(spec["q"], spec["role"])
    assert check_properties(res, spec) == []


def test_placeholders_are_substituted(reg):
    a = {"observation": "AUC {fact:academic.risk.k5.all.auc}", "basis": ["academic.risk.k5.all.auc"],
         "recommendation": "Проверить на данных вуза.", "risks": "Демо-данные."}
    assert check(a, reg, {"academic.risk.k5.all.auc"}) == []
    out = render(a, reg)
    assert out["observation"] == "AUC " + reg.display("academic.risk.k5.all.auc")
    assert "{fact:" not in out["observation"] and out["reliability"] == "демо"


def test_invented_and_unknown_numbers_rejected(reg):
    ok_ids = {"academic.risk.k5.all.auc"}
    base = {"basis": [], "recommendation": "Проверить.", "risks": "Нет."}
    assert any("число без плейсхолдера" in e for e in check({**base, "observation": "AUC 0,93"}, reg, ok_ids))
    assert any("неизвестный плейсхолдер" in e for e in check({**base, "observation": "{fact:x.y}"}, reg, ok_ids))
    assert any("не получен" in e for e in check({**base, "observation": "{fact:finance.h1.verdict}"}, reg, ok_ids))
    assert check({**base, "observation": "В 2025 году, P50 и H1 на неделе 5."}, reg, ok_ids) == []
    rec = {**base, "observation": "x", "recommendation": "Поднять долю до {fact:academic.risk.k5.all.auc}"}
    assert any("рекомендации" in e for e in check(rec, reg, ok_ids))
    assert parse("```json\n{\"a\": 1}\n```") == {"a": 1} and parse("не JSON") is None


def test_no_key_mode_keeps_briefing(reg, tmp_path):
    adv = make(None, reg, tmp_path, NOKEY)
    assert adv.ask("Как дела?", "rector").mode == "offline"
    cards = adv.briefing("rector")
    assert len(cards) >= 6 and all(c["reliability"] for c in cards)


def test_llm_errors_are_reported_not_hidden(reg, tmp_path):
    adv = make([LLMError("сервис не ответил вовремя")], reg, tmp_path)
    res = adv.ask("Насколько точна модель?", "vp_academic")
    assert not res.ok and "недоступен" in res.error


def test_log_has_no_secrets_or_personal_numbers(reg, tmp_path):
    adv = make([tool_call("academic_overview"), answer("AUC {fact:academic.risk.k5.all.auc}.",
                                                       ["academic.risk.k5.all.auc"])], reg, tmp_path)
    adv.ask("Мой ключ gsk_abcdefghijklmnop, почта a@b.kz, номер 87011234567 — какой AUC?", "vp_academic")
    log = (tmp_path / "log.jsonl").read_text(encoding="utf-8")
    assert "test-key-not-real" not in log and "gsk_abcdefghijklmnop" not in log
    assert "a@b.kz" not in log and "87011234567" not in log
    entry = json.loads(log.splitlines()[-1])
    assert entry["tools"][0]["name"] == "academic_overview"
    assert redact("в 2025 году") == "в 2025 году"


def test_role_cannot_call_other_modules(reg, tmp_path):
    from src.advisor import tools
    out = tools.call(reg, "finance_benchmark", {}, ("academic_overview",))
    assert out["facts"] == [] and "недоступен" in out["error"]
