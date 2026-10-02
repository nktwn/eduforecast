import json
import os
import time
from pathlib import Path

import requests

from src.research.config import OPENALEX_API_BASE, OPENALEX_INSTITUTION_ID, RAW_DIR

_MAILTO = os.environ.get("OPENALEX_MAILTO")


def _get(url: str, params: dict) -> dict:
    if _MAILTO:
        params = {**params, "mailto": _MAILTO}
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _cached(cache_name: str, fetch_fn) -> dict:
    cache_path = RAW_DIR / cache_name
    if cache_path.exists():
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)

    data = fetch_fn()
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return data


def fetch_institution(search_term: str = "Astana IT University") -> dict:
    return _get(f"{OPENALEX_API_BASE}/institutions", {"search": search_term})


def fetch_yearly_work_counts(institution_id: str = OPENALEX_INSTITUTION_ID) -> dict:
    def _fetch():
        time.sleep(0.1)
        return _get(
            f"{OPENALEX_API_BASE}/works",
            {"filter": f"institutions.id:{institution_id}", "group_by": "publication_year"},
        )

    return _cached(f"yearly_work_counts_{institution_id}.json", _fetch)
