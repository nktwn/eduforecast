"""OpenAlex client: the API key never reaches error messages or usage logs."""
import pytest

from src.research import openalex_client as oa


class _Resp:
    def __init__(self, status, headers=None, text=""):
        self.status_code, self.headers, self.text = status, headers or {}, text

    def json(self):
        return {}


def test_key_not_in_errors_or_usage(monkeypatch, tmp_path):
    secret = "test-secret-key-123456"
    monkeypatch.setattr(oa, "_API_KEY", secret)
    seen = {}

    def fake_get(url, params=None, timeout=None):
        seen.update(params)
        return _Resp(404, {"X-RateLimit-Credits-Used": "1", "X-RateLimit-Remaining": "9"})

    monkeypatch.setattr(oa.requests, "get", fake_get)
    with pytest.raises(RuntimeError) as exc:
        oa._request("https://api.openalex.org/works", {"filter": "x"})
    assert seen["api_key"] == secret            # the key is sent ...
    assert secret not in str(exc.value)         # ... but never reported
    row = oa.log_usage("test", path=tmp_path / "usage.csv")
    text = (tmp_path / "usage.csv").read_text()
    assert secret not in text and row["key"] == "present" and row["remaining_credits"] == 9


def test_cache_key_excludes_api_key():
    a = oa._cache_path("https://api.openalex.org/works", {"filter": "x"})
    assert "api_key" not in str(a)
