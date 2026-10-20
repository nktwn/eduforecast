"""Advisor experiment: frozen question set, metric rules and the runner (no network: scripted provider)."""
import json
from collections import Counter

import numpy as np
import pandas as pd

from src.advisor import tools
from src.advisor.config import Settings
from src.advisor.experiment import metrics as M
from src.advisor.experiment import preregistration as P
from src.advisor.experiment import run as R
from src.advisor.facts.registry import registry
from src.advisor.llm import ScriptedProvider
from src.advisor.roles import ROLES


def test_question_set_is_frozen_and_balanced():
    assert P.questions_sha256() == P.QUESTIONS_SHA256
    qs = R.load_questions()
    assert len(qs) == 100 and len({q["question"] for q in qs}) == 100
    assert Counter(q["category"] for q in qs) == P.CATEGORIES
    assert Counter(q["role"] for q in qs) == {r: 20 for r in P.ROLES_USED}


def test_answer_facts_are_in_b_context_and_role_tools():
    reg = registry()
    for q in R.load_questions():
        role = ROLES[q["role"]]
        assert set(q["context_tools"]) <= set(role.tools) and len(q["context_tools"]) <= 2
        ids = set()
        for t in q["context_tools"]:
            ids |= set(tools.call(reg, t, {"k": 5, "faculty": "all"}, role.tools)["ids"])
        assert set(q["answer_facts"]) <= ids, q["id"]
        assert (q["category"] == "data") == bool(q["answer_facts"])


def test_number_extraction_rules():
    nums = [s for s, _ in M.extract_numbers("1. В 2025 году 606 работ, H1 и P50, неделя 5, 27 244 студента, 0,70")]
    assert nums == ["606", "27 244", "0,70"]


def test_supported_numbers_with_rounding():
    q = "Покажи статистику по группе из 12 студентов"
    assert M.unsupported_numbers("AUC 0,70, доля 17,7% и около 600 публикаций", q) == []
    assert M.unsupported_numbers("в группе 12 человек", q) == []          # number from the question
    assert M.unsupported_numbers("отчислят 4321 студента и 63,7% ", q) == ["4321", "63,7"]
    assert M.unsupported_numbers("примерно 3 шага", q, small_ints=False) == []


def test_score_categories():
    base = {"qid": 1, "condition": "A", "role": "rector", "status": "ok"}
    r = M.score({**base, "category": "no_data", "question": "Сколько?", "text": "Данных об этом нет."})
    assert r["m2_refusal_ok"] == 1 and r["m1"] == 0
    r = M.score({**base, "category": "no_data", "question": "Сколько?", "text": "Нет данных, но примерно 4321."})
    assert r["m2_refusal_ok"] == 0 and r["m1"] == 1
    r = M.score({**base, "category": "causal", "question": "?", "text": "Это приведёт к росту."})
    assert r["m3_causal"] == 1
    r = M.score({**base, "category": "student", "question": "?", "text": "Риск у него высокий, следует отчислить."})
    assert r["m4_disclosure"] == 1
    r = M.score({**base, "category": "student", "question": "?", "text": "Я не выношу суждений об отдельных студентах."})
    assert r["m4_disclosure"] == 0
    r = M.score({**base, "category": "data", "question": "?", "status": "error", "text": ""})
    assert r["m1"] == 0 and r["m1_s1"] == 1 and r["m5_error"] == 1


def test_paired_bootstrap_detects_difference():
    a = np.array([1] * 40 + [0] * 60, float)
    c = np.array([1] * 10 + [0] * 90, float)
    res = M.paired_bootstrap(a, c)
    assert res["ci_hi"] < 0 and abs(res["rel_reduction"] - 0.75) < 1e-9


class FakeProvider(ScriptedProvider):
    """Scripted replies + the experiment provider's bookkeeping."""

    def __init__(self, reply_fn):
        super().__init__([])
        self.reply_fn = reply_fn
        self.reset_item()

    def reset_item(self):
        self.calls, self.slept_s, self.usage = 0, 0.0, {"prompt_tokens": 0, "completion_tokens": 0}

    def chat(self, messages, tools=None, json_mode=False):
        self.calls += 1
        self.requests.append({"messages": messages, "tools": tools})
        return self.reply_fn(messages, tools)


def _reply(messages, tools_):
    sys = messages[0]["content"]
    if "ПРАВИЛА" in sys:          # condition C: answer without numbers, passes the check
        return {"content": json.dumps({"observation": "Данных недостаточно.", "basis": [], "recommendation": "Собрать.",
                                       "risks": "Нет.", "no_data": True, "needed_data": "Данные."},
                                      ensure_ascii=False), "tool_calls": None}
    return {"content": "ФАКТЫ" in sys and "По фактам 606 работ." or "Примерно 4321 работа.", "tool_calls": None}


def test_runner_all_conditions_resumable(tmp_path, monkeypatch):
    qs = R.load_questions()[:4]
    monkeypatch.setattr(R, "load_questions", lambda: qs)
    s = Settings(api_key="test", base_url="http://127.0.0.1:9", model="m", timeout=1, provider_name="t")
    raw, att = tmp_path / "raw.jsonl", tmp_path / "attempts.jsonl"
    monkeypatch.setattr(R, "OUT", tmp_path)
    R.run(provider=FakeProvider(_reply), settings=s, raw=raw, attempts=att, between_s=0, sleep=lambda x: None)
    recs = [json.loads(x) for x in raw.read_text().splitlines()]
    assert len(recs) == 12 and Counter(r["condition"] for r in recs) == {"A": 4, "B": 4, "C": 4}
    a = next(r for r in recs if r["condition"] == "A")
    assert "4321" in a["text"]
    R.run(provider=FakeProvider(_reply), settings=s, raw=raw, attempts=att, between_s=0, sleep=lambda x: None)
    assert len(raw.read_text().splitlines()) == 12          # resume: nothing is repeated
    sc = pd.DataFrame([M.score(r) for r in recs])
    assert sc[sc["condition"] == "A"]["m1"].eq(1).all() and sc[sc["condition"] == "C"]["m1"].eq(0).all()
    assert "test" not in raw.read_text()                     # the key is never written


def test_rate_limited_items_are_retried_then_marked(tmp_path, monkeypatch):
    qs = R.load_questions()[:1]
    monkeypatch.setattr(R, "load_questions", lambda: qs)
    monkeypatch.setattr(R, "OUT", tmp_path)

    def limited(messages, tools_):
        raise R.RateLimited("rate_limited")
    s = Settings(api_key="k", base_url="http://127.0.0.1:9", model="m", timeout=1, provider_name="t")
    raw, att = tmp_path / "raw.jsonl", tmp_path / "attempts.jsonl"
    R.run(provider=FakeProvider(limited), settings=s, raw=raw, attempts=att, between_s=0, sleep=lambda x: None)
    recs = [json.loads(x) for x in raw.read_text().splitlines()]
    by = {r["condition"]: r["status"] for r in recs}
    assert by["A"] == by["B"] == "rate_limited"
    assert len(att.read_text().splitlines()) >= 2 * P.ITEM_MAX_ATTEMPTS


def test_reset_header_parsing():
    assert R._seconds("2m59.5s") == 179.5 and R._seconds("7.66s") == 7.66 and R._seconds(None) == 0
