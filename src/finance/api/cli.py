import argparse
import json
import sys

from src.finance.api.contract import validate
from src.finance.api.providers import DemoProvider, MockProvider


def main():
    parser = argparse.ArgumentParser(description="Print a finance forecast response (contract finance-forecast/0.1.0)")
    parser.add_argument("query", help="series_id, UNITID or part of the institution name")
    parser.add_argument("--provider", choices=["demo", "mock"], default="demo")
    args = parser.parse_args()

    provider = DemoProvider() if args.provider == "demo" else MockProvider()
    hits = provider.search(args.query, limit=1)
    if not hits:
        print(f"No institution matches {args.query!r}", file=sys.stderr)
        raise SystemExit(1)
    response = provider.forecast(hits[0]["series_id"])
    errors = validate(response)
    print(json.dumps(response, ensure_ascii=False, indent=2))
    if errors:
        print("\n".join(errors), file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
