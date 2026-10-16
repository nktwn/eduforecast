"""Advisor settings from environment variables (.env) or Streamlit secrets; no secrets in code."""
from __future__ import annotations

import os
from dataclasses import dataclass

from src.config import BASE_DIR

DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_MODEL = "openai/gpt-oss-120b"
DEFAULT_TIMEOUT = 30.0
LOG_PATH = BASE_DIR / "logs" / "advisor_queries.jsonl"


@dataclass(frozen=True)
class Settings:
    api_key: str
    base_url: str
    model: str
    timeout: float
    provider_name: str

    @property
    def has_key(self) -> bool:
        return bool(self.api_key)

    def public(self) -> dict:
        """Safe to show or log: never contains the key."""
        return {"provider": self.provider_name, "base_url": self.base_url, "model": self.model,
                "timeout": self.timeout, "key_present": self.has_key}


def _secret(name: str) -> str:
    value = os.getenv(name, "")
    if value:
        return value
    try:  # .streamlit/secrets.toml, only inside a Streamlit app
        import streamlit as st

        return str(st.secrets.get(name, ""))
    except Exception:
        return ""


def load_settings() -> Settings:
    try:
        from dotenv import load_dotenv

        load_dotenv(BASE_DIR / ".env")
    except ImportError:
        pass
    key = _secret("ADVISOR_API_KEY") or _secret("GROQ_API_KEY")
    base = _secret("ADVISOR_BASE_URL") or DEFAULT_BASE_URL
    return Settings(api_key=key, base_url=base.rstrip("/"), model=_secret("ADVISOR_MODEL") or DEFAULT_MODEL,
                    timeout=float(_secret("ADVISOR_TIMEOUT") or DEFAULT_TIMEOUT),
                    provider_name="groq" if "groq.com" in base else "openai-compatible")
