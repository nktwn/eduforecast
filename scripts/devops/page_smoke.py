"""Render every page of the app navigation with Streamlit AppTest and fail on any exception.

No network, no LLM key, no datasets are needed: pages without data show empty states.
The page list is read from app/main.py (calls to page("pages/...")), so new pages are
covered automatically. Usage: python scripts/devops/page_smoke.py
"""
from __future__ import annotations

import ast
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app"


def navigation_pages() -> list[str]:
    tree = ast.parse((APP / "main.py").read_text(encoding="utf-8"))
    pages = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "page"
                and node.args and isinstance(node.args[0], ast.Constant)):
            pages.append(node.args[0].value)
    return pages


def main() -> int:
    for name in ("GROQ_API_KEY", "ADVISOR_API_KEY"):
        os.environ[name] = ""
    for p in (APP, ROOT):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    from streamlit.testing.v1 import AppTest

    pages = navigation_pages() + ["main.py"]
    if len(pages) < 2:
        print("page_smoke: no pages found in app/main.py", file=sys.stderr)
        return 2
    failed = 0
    for page in pages:
        start = time.monotonic()
        at = AppTest.from_file(str(APP / page), default_timeout=300)
        at.run()
        errors = [e.value for e in at.exception]
        status = "OK" if not errors else "FAIL"
        failed += bool(errors)
        print(f"{status:4} {page:32} {time.monotonic() - start:5.1f}s {errors if errors else ''}")
    print(f"page_smoke: {len(pages) - failed}/{len(pages)} pages rendered without exceptions")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
