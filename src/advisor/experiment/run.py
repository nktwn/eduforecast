"""Run conditions A, B, C on the frozen question set (src/advisor/experiment/preregistration.py).

  python -m src.advisor.experiment.run            # resumable; raw answers -> results/advisor_experiment/raw.jsonl
  python -m src.advisor.experiment.run --dry      # order and context sizes only, no LLM call

The key is read from .env by src/advisor/config.py and is never written to the output.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import time
from datetime import datetime, timezone

import requests

from src.advisor import tools
from src.advisor.config import Settings, load_settings
from src.advisor.core import Advisor
from src.advisor.experiment import preregistration as P
from src.advisor.facts.registry import Registry, registry
from src.advisor.llm import LLMError
from src.advisor.roles import ROLES
from src.config import BASE_DIR

OUT = BASE_DIR / "results" / "advisor_experiment"
RAW = OUT / "raw.jsonl"
ATTEMPTS = OUT / "attempts.jsonl"   # every rate-limited attempt (the item is retried later)


class RateLimited(LLMError):
    pass


def _seconds(value: str | None) -> float:
    """Groq reset headers look like '7.66s', '2m59.56s', '1h2m3s'."""
    if not value:
        return 0.0
    total = 0.0
    for num, unit in re.findall(r"([\d.]+)(ms|h|m|s)", value):
        total += float(num) * {"ms": 0.001, "h": 3600, "m": 60, "s": 1}[unit]
    return total


class ExperimentProvider:
    """OpenAI-compatible chat client with the experiment's temperature/max_tokens and free-tier pacing."""

    def __init__(self, settings: Settings, sleep=time.sleep):
        self.s = settings
        self.sleep = sleep
        self.remaining_tokens: int | None = None
        self.reset_tokens_s = 0.0
        self.reset_at = 0.0
        self.reset_item()

    def reset_item(self):
        self.calls, self.slept_s, self.usage = 0, 0.0, {"prompt_tokens": 0, "completion_tokens": 0}

    def _wait(self, seconds: float):
        seconds = min(max(seconds, 1.0), P.MAX_WAIT_S)
        self.slept_s += seconds
        self.sleep(seconds)

    def _pace(self, body: dict):
        est = len(json.dumps(body["messages"], ensure_ascii=False)) / 2.5 + P.MAX_TOKENS
        if self.remaining_tokens is not None and self.remaining_tokens < est:
            left = self.reset_at - time.time()
            if left > 0:
                self._wait(left + 1)

    def chat(self, messages, tools=None, json_mode=False) -> dict:
        body = {"model": self.s.model, "messages": messages, "temperature": P.TEMPERATURE,
                "max_tokens": P.MAX_TOKENS}
        if tools:
            body["tools"], body["tool_choice"] = tools, "auto"
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        headers = {"Authorization": f"Bearer {self.s.api_key}", "Content-Type": "application/json"}
        for attempt in range(P.CALL_MAX_RETRIES + 1):
            self._pace(body)
            try:
                r = requests.post(f"{self.s.base_url}/chat/completions", json=body, headers=headers,
                                  timeout=max(self.s.timeout, 60))
            except requests.exceptions.RequestException as e:
                raise LLMError(f"сеть: {type(e).__name__}") from e
            self.calls += 1
            rem = r.headers.get("x-ratelimit-remaining-tokens")
            self.remaining_tokens = int(float(rem)) if rem else None
            self.reset_at = time.time() + _seconds(r.headers.get("x-ratelimit-reset-tokens"))
            if r.status_code != 429:
                break
            if attempt == P.CALL_MAX_RETRIES:
                raise RateLimited("rate_limited")
            try:
                wait = float(r.headers.get("retry-after", "10"))
            except ValueError:
                wait = 10.0
            self._wait(wait + 1)
        if r.status_code == 413:
            raise LLMError("413 запрос слишком велик")
        if r.status_code == 400 and tools and "tool" in r.text.lower():
            raise LLMError("tools_unsupported")
        if r.status_code != 200:
            raise LLMError(f"код ответа API {r.status_code}: {r.text[:200]}")
        data = r.json()
        for k in self.usage:
            self.usage[k] += int((data.get("usage") or {}).get(k) or 0)
        msg = data["choices"][0]["message"]
        return {"content": msg.get("content"), "tool_calls": msg.get("tool_calls")}


def load_questions() -> list[dict]:
    if P.questions_sha256() != P.QUESTIONS_SHA256:
        raise SystemExit("questions.json differs from the pre-registered sha256: the set is frozen")
    return json.loads(P.QUESTIONS_PATH.read_text(encoding="utf-8"))


def b_context(reg: Registry, q: dict) -> str:
    role = ROLES[q["role"]]
    payload = {}
    for name in q["context_tools"]:
        args = {"k": P.K, "faculty": P.FACULTY} if name in ("academic_overview", "risk_groups") else {}
        out = tools.call(reg, name, args, role.tools)
        payload[name] = {"facts": [{k: v for k, v in f.items() if k != "placeholder"} for f in out["facts"]],
                         "caveats": out["caveats"]}
    return json.dumps(payload, ensure_ascii=False)


def run_plain(provider, q: dict, system: str) -> dict:
    msg = provider.chat([{"role": "system", "content": system}, {"role": "user", "content": q["question"]}])
    return {"text": msg.get("content") or "", "answer": None}


def run_full(provider, reg: Registry, settings: Settings, q: dict) -> dict:
    adv = Advisor(provider=provider, settings=settings, reg=reg, log_path=OUT / "advisor_c_queries.jsonl")
    res = adv.ask(q["question"], role_id=q["role"], k=P.K, faculty=P.FACULTY)
    if res.ok:
        a = res.answer
        text = "\n".join(x for x in (a["observation"], a["recommendation"], a["risks"], a["needed_data"]) if x)
    else:
        text = res.error
    return {"text": text, "answer": {"no_data": bool(res.answer and res.answer["no_data"])} if res.ok else None,
            "c_ok": res.ok, "c_mode": res.mode, "c_raw": res.raw, "c_tools": res.tools_called,
            "c_validation_errors": res.validation_errors, "c_error": res.error}


def item_order(questions: list[dict]) -> list[tuple[int, str]]:
    items = [(q["id"], c) for q in questions for c in P.CONDITIONS]
    random.Random(P.SEED).shuffle(items)
    return items


def done_items(path=RAW) -> set[tuple[int, str]]:
    if not path.exists():
        return set()
    return {(r["qid"], r["condition"]) for r in map(json.loads, path.read_text(encoding="utf-8").splitlines())
            if r.get("status") in ("ok", "error", "rate_limited")}


def _append(path, rec: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")


def run_item(provider, reg, settings, q: dict, cond: str) -> dict:
    role = ROLES[q["role"]]
    provider.reset_item()
    t0 = time.time()
    if cond == "A":
        out = run_plain(provider, q, P.SYSTEM_A.format(role=role.name, tone=role.tone))
    elif cond == "B":
        out = run_plain(provider, q, P.SYSTEM_B.format(role=role.name, tone=role.tone, facts=b_context(reg, q)))
    else:
        out = run_full(provider, reg, settings, q)
        if not out["c_ok"] and "rate_limited" in (out.get("c_error") or ""):  # Advisor wraps the provider error
            raise RateLimited("rate_limited")
    status = "ok" if cond != "C" or out["c_ok"] else "error"
    return {**out, "status": status, "latency_s": round(time.time() - t0 - provider.slept_s, 3),
            "slept_s": round(provider.slept_s, 1), "calls": provider.calls, "usage": dict(provider.usage)}


def run(provider=None, settings: Settings | None = None, reg: Registry | None = None, raw=RAW, attempts=ATTEMPTS,
        between_s: float = 2.0, sleep=time.sleep):
    settings = settings or load_settings()
    if not settings.has_key:
        raise SystemExit("нет ключа LLM в .env")
    reg = reg or registry()
    provider = provider or ExperimentProvider(settings, sleep=sleep)
    questions = {q["id"]: q for q in load_questions()}
    queue = [it for it in item_order(list(questions.values())) if it not in done_items(raw)]
    tries: dict[tuple[int, str], int] = {}
    while queue:
        qid, cond = queue.pop(0)
        q = questions[qid]
        base = {"qid": qid, "condition": cond, "role": q["role"], "category": q["category"], "question": q["question"],
                "model": settings.model, "ts": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        try:
            rec = {**base, **run_item(provider, reg, settings, q, cond)}
        except RateLimited:
            tries[(qid, cond)] = tries.get((qid, cond), 0) + 1
            _append(attempts, {**base, "attempt": tries[(qid, cond)], "status": "rate_limited_attempt"})
            if tries[(qid, cond)] < P.ITEM_MAX_ATTEMPTS:
                queue.append((qid, cond))
                sleep(60)
                continue
            rec = {**base, "status": "rate_limited", "text": "", "latency_s": None}
        except LLMError as e:
            rec = {**base, "status": "error", "text": "", "error": str(e), "latency_s": None,
                   "calls": provider.calls, "usage": dict(provider.usage)}
        _append(raw, rec)
        print(f"{len(done_items(raw)):3d}/300 q{qid:03d} {cond} {rec['status']} "
              f"calls={rec.get('calls')} lat={rec.get('latency_s')} slept={rec.get('slept_s')}", flush=True)
        sleep(between_s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    if a.dry:
        qs = load_questions()
        reg = registry()
        print("sha256 ok; items:", len(item_order(qs)), "first 6:", item_order(qs)[:6])
        print("max B context chars:", max(len(b_context(reg, q)) for q in qs))
        return
    run()


if __name__ == "__main__":
    main()
