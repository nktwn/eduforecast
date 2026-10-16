"""LLM providers behind one interface: OpenAI-compatible chat completions (Groq by default)."""
from __future__ import annotations

import json
import time
from typing import Protocol

import requests

from src.advisor.config import Settings


RATE_LIMIT_RETRIES = 2


class LLMError(RuntimeError):
    pass


class LLMProvider(Protocol):
    def chat(self, messages: list[dict], tools: list[dict] | None = None, json_mode: bool = False) -> dict:
        """Returns the assistant message: {"content": str | None, "tool_calls": [...] | None}."""


class OpenAICompatibleProvider:
    def __init__(self, settings: Settings):
        self.s = settings

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.s.api_key}", "Content-Type": "application/json"}

    def chat(self, messages, tools=None, json_mode=False) -> dict:
        body = {"model": self.s.model, "messages": messages, "temperature": 0.2, "max_tokens": 1500}
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        for attempt in range(RATE_LIMIT_RETRIES + 1):
            try:
                r = requests.post(f"{self.s.base_url}/chat/completions", json=body, headers=self._headers(),
                                  timeout=self.s.timeout)
            except requests.exceptions.Timeout as e:
                raise LLMError("сервис не ответил вовремя") from e
            except requests.exceptions.RequestException as e:
                raise LLMError("нет соединения с сервисом") from e
            if r.status_code != 429 or attempt == RATE_LIMIT_RETRIES:
                break
            try:
                wait = float(r.headers.get("retry-after", "5"))
            except ValueError:
                wait = 5.0
            time.sleep(min(max(wait, 1.0), 30.0))
        if r.status_code == 429:
            raise LLMError("превышен лимит запросов к сервису, попробуйте через минуту")
        if r.status_code == 413:
            raise LLMError("запрос слишком велик для модели")
        if r.status_code in (401, 403):
            raise LLMError("ключ API недействителен")
        if r.status_code == 400 and tools and "tool" in r.text.lower():
            raise LLMError("tools_unsupported")
        if r.status_code != 200:
            raise LLMError(f"код ответа API {r.status_code}")
        try:
            msg = r.json()["choices"][0]["message"]
        except (ValueError, KeyError, IndexError) as e:
            raise LLMError("неожиданный ответ сервиса") from e
        return {"content": msg.get("content"), "tool_calls": msg.get("tool_calls")}


def key_status(settings: Settings) -> str:
    """'нет' / 'есть' / 'недействителен' / 'не проверен' (no network)."""
    if not settings.has_key:
        return "нет"
    try:
        r = requests.get(f"{settings.base_url}/models", headers={"Authorization": f"Bearer {settings.api_key}"},
                         timeout=min(settings.timeout, 10))
    except requests.exceptions.RequestException:
        return "не проверен"
    if r.status_code in (401, 403):
        return "недействителен"
    return "есть" if r.status_code == 200 else "не проверен"


class ScriptedProvider:
    """Test double: returns pre-scripted assistant messages in order and records the requests."""

    def __init__(self, replies: list[dict | str]):
        self.replies = list(replies)
        self.requests: list[dict] = []

    def chat(self, messages, tools=None, json_mode=False) -> dict:
        self.requests.append({"messages": messages, "tools": tools, "json_mode": json_mode})
        if not self.replies:
            raise LLMError("script exhausted")
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        if isinstance(reply, str):
            return {"content": reply, "tool_calls": None}
        if "answer" in reply:
            return {"content": json.dumps(reply["answer"], ensure_ascii=False), "tool_calls": None}
        return reply
