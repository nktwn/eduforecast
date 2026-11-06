"""Precompute heavy app results so pages open fast (data/app_cache/, not in git).

  python scripts/prepare_app.py          # ~2-4 min: OULAD, risk model for k = 5/10/20 x 7 faculties, Prophet

The same functions as in the pages are called; results are persisted with a signature of the source
files. Models are not retrained when the cache is valid.
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "app"):
    sys.path.insert(0, str(p))

from components import app_cache  # noqa: E402
from components import data_loader, research_data_loader  # noqa: E402


def main():
    t0 = time.time()
    sig = app_cache.oulad_signature()
    if (ROOT / "data" / "raw" / "studentInfo.csv").exists():
        app_cache.save("oulad_raw", sig, data_loader._read_raw_csv())
        print(f"OULAD raw cached ({time.time() - t0:.0f}s)", flush=True)
        for k in data_loader.K_OPTIONS:
            for code in data_loader.FACULTY_MAP:
                app_cache.save(f"risk_{code}_k{k}", sig, data_loader.compute_risk_model(code, k))
            print(f"risk model k={k} cached ({time.time() - t0:.0f}s)", flush=True)
    else:
        print("OULAD data missing: academic cache skipped")
    app_cache.save("research_forecast", app_cache.research_signature(),
                   research_data_loader.compute_forecast_comparison())
    print(f"research forecast cached ({time.time() - t0:.0f}s) → {app_cache.CACHE_DIR}")


if __name__ == "__main__":
    main()
