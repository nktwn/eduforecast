import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import nbformat as nbf

from src.research.config import LOGISTIC_CAP_MULTIPLIER

nb = nbf.v4.new_notebook()
cells = []

cells.append(nbf.v4.new_markdown_cell(
    "# 07 — Research Module: Scientific Productivity Forecast\n"
    "**EduForecast** | OpenAlex API | Notebook 7\n\n"
    "Forecasts yearly publication counts for Astana IT University using the "
    "public OpenAlex API, comparing Prophet `growth='linear'` vs "
    "`growth='logistic'`.\n\n"
    "**Scope limitation (read before trusting any number below):** this "
    "fits on **6-7 yearly data points** (2020-2026; 2019 excluded, see cell "
    "below). That is far too little data for a high-precision forecast — "
    "confidence intervals are wide by construction, and the only validation "
    "performed is a single leave-last-year-out sanity check, not "
    "cross-validation. Treat this as a proof-of-concept for the modelling "
    "pipeline, not a production-grade forecast."
))

cells.append(nbf.v4.new_code_cell(
    "import sys\n"
    "import warnings\n"
    "from pathlib import Path\n\n"
    "import matplotlib\n"
    "matplotlib.use('Agg')\n"
    "import matplotlib.pyplot as plt\n"
    "import pandas as pd\n\n"
    "warnings.filterwarnings('ignore')\n\n"
    "PROJECT_ROOT = Path.cwd().parent\n"
    "if str(PROJECT_ROOT) not in sys.path:\n"
    "    sys.path.insert(0, str(PROJECT_ROOT))\n\n"
    "from src.research.aggregate import build_yearly_counts, filter_training_window, to_prophet_frame\n"
    "from src.research.config import (\n"
    "    FIGURES_DIR, METRICS_DIR, OPENALEX_INSTITUTION_NAME,\n"
    "    TRAINING_YEAR_MIN, TRAINING_YEAR_MAX, LOGISTIC_CAP_MULTIPLIER,\n"
    ")\n"
    "from src.research.forecast import run_forecast_comparison\n\n"
    "print(f'Institution: {OPENALEX_INSTITUTION_NAME}')\n"
    "print(f'Training window: {TRAINING_YEAR_MIN}-{TRAINING_YEAR_MAX}')"
))

cells.append(nbf.v4.new_markdown_cell("## 1. Collect & Aggregate (OpenAlex)"))

cells.append(nbf.v4.new_code_cell(
    "full_counts = build_yearly_counts()\n"
    "full_counts"
))

cells.append(nbf.v4.new_code_cell(
    "# 2019 is excluded: a single indexed publication that year reflects the\n"
    "# institution's pre-registration/startup period, not an actual annual\n"
    "# publication rate. Including it would distort both the trend fit and\n"
    "# the logistic cap computed below.\n"
    "training = filter_training_window(full_counts)\n"
    "training"
))

cells.append(nbf.v4.new_markdown_cell(
    "## 2. Forecast: linear vs logistic growth\n\n"
    f"The logistic variant needs a saturating `cap`. There is no way to "
    f"derive this from 7 points, so it is set explicitly as an **expert "
    f"guess** (current peak × {LOGISTIC_CAP_MULTIPLIER:g}, see "
    "`src/research/config.py::LOGISTIC_CAP_MULTIPLIER`), not a value fit "
    "from the data."
))

cells.append(nbf.v4.new_code_cell(
    "comparison = run_forecast_comparison(training)\n"
    "print(f'Logistic cap (expert guess): {comparison.logistic_cap:.0f}')\n"
    "comparison.linear_forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].tail(4)"
))

cells.append(nbf.v4.new_code_cell(
    "comparison.logistic_forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].tail(4)"
))

cells.append(nbf.v4.new_code_cell(
    "fig, ax = plt.subplots(figsize=(9, 5))\n"
    "ax.plot(training['year'], training['works_count'], 'o-', color='#0f172a', label='Факт')\n\n"
    "last_year = training['year'].max()\n"
    "for fcst, label, color in (\n"
    "    (comparison.linear_forecast, 'Прогноз (linear)', '#2563eb'),\n"
    "    (comparison.logistic_forecast, 'Прогноз (logistic)', '#059669'),\n"
    "):\n"
    "    future = fcst[fcst['ds'].dt.year > last_year].copy()\n"
    "    future['year'] = future['ds'].dt.year\n"
    "    ax.plot(future['year'], future['yhat'], '--o', color=color, label=label)\n"
    "    ax.fill_between(future['year'], future['yhat_lower'], future['yhat_upper'], color=color, alpha=0.15)\n\n"
    "ax.axhline(comparison.logistic_cap, color='#6b7280', linestyle=':', linewidth=1,\n"
    "           label=f'Logistic cap (expert guess) = {comparison.logistic_cap:.0f}')\n"
    "ax.set_xlabel('Год'); ax.set_ylabel('Публикаций в год')\n"
    "ax.set_title(f'{OPENALEX_INSTITUTION_NAME}: прогноз научной продуктивности')\n"
    "ax.legend()\n"
    "fig.tight_layout()\n"
    "fig.savefig(FIGURES_DIR / '07_forecast_comparison.png', dpi=150)\n"
    "plt.show()"
))

cells.append(nbf.v4.new_markdown_cell(
    "## 3. Backtest (sanity check, NOT cross-validation)\n\n"
    "Train on 2020-2025, predict 2026, compare against the actual observed "
    "count (753). With only 6-7 yearly points there is not enough data for "
    "a statistically meaningful k-fold or time-series cross-validation — "
    "this is a single held-out-year sanity check, named as such on purpose."
))

cells.append(nbf.v4.new_code_cell(
    "bt = comparison.backtest\n"
    "print(f'Backtest year: {bt.backtest_year}')\n"
    "print(f'Actual: {bt.actual:.0f}')\n"
    "print()\n"
    "for growth, res in bt.predictions.items():\n"
    "    print(f\"{growth:10s} predicted={res['predicted']:6.0f}  \"\n"
    "          f\"[{res['lower']:.0f}, {res['upper']:.0f}]  \"\n"
    "          f\"abs_error={res['abs_error']:6.1f}  pct_error={res['pct_error']:5.1f}%\")\n"
    "print()\n"
    "print(bt.note)"
))

cells.append(nbf.v4.new_code_cell(
    "backtest_df = pd.DataFrame([\n"
    "    {'growth': g, 'backtest_year': bt.backtest_year, 'actual': bt.actual, **res}\n"
    "    for g, res in bt.predictions.items()\n"
    "])\n"
    "backtest_df.to_csv(METRICS_DIR / 'research_backtest.csv', index=False)\n"
    "backtest_df"
))

cells.append(nbf.v4.new_markdown_cell(
    "## 4. Summary\n\n"
    "- Data source: OpenAlex API, institution ID `I4405257690` (Astana IT "
    "University), aggregated at the whole-institution level (no "
    "per-department breakdown — OpenAlex doesn't expose clean sub-institution "
    "IDs; see PROJECT_STATUS.md §4.4).\n"
    "- Training window: 2020-2026 (7 points), 2019 dropped as a non-representative "
    "startup-period outlier.\n"
    "- Two Prophet variants compared: `linear` (no ceiling) and `logistic` "
    "(ceiling = expert-guessed cap, not data-derived).\n"
    "- Validation: one leave-last-year-out sanity check, explicitly not a "
    "cross-validation, given the small N.\n"
    "- **This is a proof-of-concept.** Revisit the logistic cap and re-run "
    "the backtest once a few more years of data are available."
))

nb["cells"] = cells
nb["metadata"] = {
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python", "version": "3.12"},
}

out_path = Path(__file__).parent / "07_research_forecast.ipynb"
with open(out_path, "w", encoding="utf-8") as f:
    nbf.write(nb, f)

print(f"Wrote {out_path}")
