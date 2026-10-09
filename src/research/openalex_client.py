import hashlib
import json
import os
import time
from pathlib import Path

import requests

from src.research.config import OPENALEX_API_BASE, OPENALEX_INSTITUTION_ID, RAW_DIR

_MAILTO = os.environ.get("OPENALEX_MAILTO")
_API_KEY = os.environ.get("OPENALEX_API_KEY")

HTTP_CACHE_DIR: Path = RAW_DIR / "http"
HTTP_CACHE_DIR.mkdir(parents=True, exist_ok=True)

MAX_RETRIES = 5
MIN_INTERVAL_S = 0.12
BUDGET_RESERVE_USD = 0.002


class BudgetExhausted(RuntimeError):
    pass


class _State:
    last_call = 0.0
    remaining_usd: float | None = None
    calls = 0
    cost_usd = 0.0


def budget() -> dict:
    return {
        "calls": _State.calls,
        "cost_usd": round(_State.cost_usd, 4),
        "remaining_usd": _State.remaining_usd,
    }


def _cache_path(url: str, params: dict) -> Path:
    key = url + "?" + "&".join(f"{k}={params[k]}" for k in sorted(params))
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
    return HTTP_CACHE_DIR / digest[:2] / f"{digest}.json"


def _request(url: str, params: dict) -> dict:
    full = dict(params)
    if _MAILTO:
        full["mailto"] = _MAILTO
    if _API_KEY:
        full["api_key"] = _API_KEY

    if _State.remaining_usd is not None and _State.remaining_usd < BUDGET_RESERVE_USD:
        raise BudgetExhausted(f"OpenAlex daily budget nearly exhausted: {budget()}")

    for attempt in range(MAX_RETRIES):
        wait = MIN_INTERVAL_S - (time.monotonic() - _State.last_call)
        if wait > 0:
            time.sleep(wait)
        _State.last_call = time.monotonic()
        try:
            resp = requests.get(url, params=full, timeout=60)
        except (requests.ConnectionError, requests.Timeout):
            time.sleep(2 ** attempt)
            continue

        remaining = resp.headers.get("X-RateLimit-Remaining-USD")
        if remaining is not None:
            _State.remaining_usd = float(remaining)
        _State.cost_usd += float(resp.headers.get("X-RateLimit-Cost-USD") or 0)
        _State.calls += 1

        if resp.status_code == 429:
            if _State.remaining_usd is not None and _State.remaining_usd < BUDGET_RESERVE_USD:
                raise BudgetExhausted(f"OpenAlex daily budget exhausted: {budget()}")
            time.sleep(float(resp.headers.get("Retry-After") or 2 ** (attempt + 1)))
            continue
        if resp.status_code >= 500:
            time.sleep(2 ** (attempt + 1))
            continue
        resp.raise_for_status()
        return resp.json()

    raise RuntimeError(f"OpenAlex request failed after {MAX_RETRIES} attempts: {url} {params}")


def get(path: str, params: dict | None = None, use_cache: bool = True, transform=None) -> dict:
    url = f"{OPENALEX_API_BASE}/{path.lstrip('/')}"
    params = params or {}
    cache_path = _cache_path(url, params)
    if use_cache and cache_path.exists():
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)

    data = _request(url, params)
    if transform is not None:
        data = transform(data)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = cache_path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    tmp.replace(cache_path)
    return data


def group_by(filter_: str, field: str) -> list[dict]:
    data = get("works", {"filter": filter_, "group_by": field, "per_page": 200})
    return data["group_by"]


def iter_works(filter_: str, select: str, per_page: int = 200, transform=None):
    page = 1
    while True:
        params = {"filter": filter_, "select": select, "per_page": per_page, "page": page}
        data = get("works", params, transform=transform)
        results = data["results"]
        yield from results
        if len(results) < per_page or page * per_page >= data["meta"]["count"]:
            return
        page += 1


def fetch_institution(institution_id: str) -> dict:
    return get(f"institutions/{institution_id}")


def fetch_ror(ror_url: str) -> dict:
    ror_id = ror_url.rstrip("/").rsplit("/", 1)[-1]
    cache_path = RAW_DIR / "ror" / f"{ror_id}.json"
    if cache_path.exists():
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)
    resp = requests.get(f"https://api.ror.org/v2/organizations/{ror_id}", timeout=30)
    resp.raise_for_status()
    data = resp.json()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return data


def fetch_yearly_work_counts(institution_id: str = OPENALEX_INSTITUTION_ID) -> dict:
    snapshot = RAW_DIR / f"yearly_work_counts_{institution_id}.json"
    if snapshot.exists():
        with open(snapshot, "r", encoding="utf-8") as f:
            return json.load(f)
    data = get("works", {"filter": f"institutions.id:{institution_id}", "group_by": "publication_year"})
    with open(snapshot, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return data
