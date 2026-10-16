"""Fact registry: build from saved results, save a snapshot, load and query it.

  python -m src.advisor.facts.registry          # rebuild src/advisor/facts/snapshot.json

The snapshot holds aggregates only (no per-student or per-registration data) and is committed,
so the app and the advisor work in a fresh clone; the build time is stored with it.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from src.advisor.facts import builders
from src.advisor.facts.fmt import format_value
from src.advisor.facts.schema import Fact, validate_all

SNAPSHOT_PATH = Path(__file__).with_name("snapshot.json")
BUILDERS = [builders.academic, builders.research, builders.finance, builders.aitu, builders.capabilities]


def build() -> list[Fact]:
    built_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    facts = [f for b in BUILDERS for f in b()]
    for f in facts:
        f.built_at = built_at
    errors = validate_all(facts)
    if errors:
        raise ValueError("invalid facts:\n" + "\n".join(errors[:20]))
    return facts


def save(facts: list[Fact], path: Path = SNAPSHOT_PATH) -> None:
    payload = {"built_at": facts[0].built_at if facts else None, "n_facts": len(facts),
               "facts": [f.to_dict() for f in facts]}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1, default=float) + "\n", encoding="utf-8")


class Registry:
    def __init__(self, facts: list[dict], built_at: str | None):
        self.facts = {f["id"]: f for f in facts}
        self.built_at = built_at

    @classmethod
    def load(cls, path: Path = SNAPSHOT_PATH) -> "Registry":
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(data["facts"], data.get("built_at"))

    def get(self, fid: str) -> dict | None:
        return self.facts.get(fid)

    def display(self, fid: str) -> str:
        f = self.facts[fid]
        return format_value(f["value"], f["unit"])

    def select(self, prefix: str = "", module: str | None = None, tag: str | None = None,
               status: str | None = None) -> list[dict]:
        out = [f for f in self.facts.values() if f["id"].startswith(prefix)]
        if module:
            out = [f for f in out if f["module"] == module]
        if tag:
            out = [f for f in out if tag in f.get("tags", [])]
        if status:
            out = [f for f in out if f["status"] == status]
        return out

    def attention(self) -> list[dict]:
        return [f for f in self.facts.values() if f.get("attention")]


@lru_cache(maxsize=1)
def registry() -> Registry:
    return Registry.load()


def main():
    facts = build()
    save(facts)
    by_status = {}
    for f in facts:
        by_status[f.status] = by_status.get(f.status, 0) + 1
    print(f"{len(facts)} facts → {SNAPSHOT_PATH}", by_status)


if __name__ == "__main__":
    main()
