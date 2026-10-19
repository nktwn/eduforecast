"""Research stage 3 pre-registration, committed BEFORE the panel is extended and before any new model.

The stage-2 criterion (src/research/stage2_config.py) is imported and not changed. This file fixes in
advance: university selection for the extended panel, data rules, targets, criteria C1 and C2, the new
international targets and hypothesis, the power analysis, the models and the evaluation designs.
"""
from src.research.stage2_config import (  # noqa: F401  (stage-2 criterion, unchanged)
    BOOTSTRAP_SAMPLES,
    CALIBRATION_ORIGINS,
    EVAL_ORIGINS,
    INNER_VALIDATION_ORIGINS,
    LAST_COMPLETE_YEAR,
    LGBM_FIXED,
    LGBM_GRID,
    RANDOM_SEED,
    RIDGE_GRID,
    SUCCESS_CI_LEVEL,
    SUCCESS_MIN_RELATIVE_MAE_GAIN,
    SUCCESS_RULE,
)

# ── 1. University selection (objective attributes only, never outcome values) ─────────────────

PANEL_YEARS = (2010, 2025)          # 2026 is partial and never used
SELECTION_SNAPSHOT = "OpenAlex institutions endpoint and ROR API on the extraction date (saved with the panel)"
GROUP_A = {
    "name": "kz_1000",
    "rule": "Institutions with country_code KZ and type education (OpenAlex) whose OpenAlex works_count "
            "(all years) is >= 1000 on the extraction date.",
    "country_codes": ["KZ"], "min_works_count": 1000,
}
REGION_COUNTRIES = {  # Central Asia, South Caucasus, Turkey, Eastern Europe
    "central_asia": ["KZ", "UZ", "KG", "TJ", "TM"],
    "south_caucasus": ["AZ", "AM", "GE"],
    "turkey": ["TR"],
    "eastern_europe": ["RU", "BY", "UA", "MD", "PL", "CZ", "SK", "HU", "RO", "BG", "LT", "LV", "EE"],
}
TECH_NAME_PATTERN = (r"(technolog|technical|polytechnic|politehn|informat|information|computer|"
                     r"\bIT\b|artificial intelligence|\bAI\b|engineering|science and technology|"
                     r"institute of science)")
GROUP_B = {
    "name": "young_tech",
    "rule": "Young technical/IT universities: OpenAlex type education, ROR 'established' >= 2000, English "
            "display name matching TECH_NAME_PATTERN (case-insensitive), OpenAlex works_count >= 1000. "
            "All such institutions in REGION_COUNTRIES are candidates; from the rest of the world the "
            "candidates are drawn at random (seed RANDOM_SEED) until the panel reaches TARGET_PANEL_SIZE.",
    "established_min": 2000, "min_works_count": 1000,
}
GROUP_C = {"name": "current_panel", "rule": "All 14 universities of the stage-2 panel stay candidates "
                                            "(SDU keeps its stage-2 status: sensitivity only)."}
TARGET_PANEL_SIZE = (40, 60)
SERIES_RULE = ("A university's series enters the panel only if it has >= 8 consecutive years within "
               "2010-2025 with >= 20 works each; the series starts at the first year of its longest such run.")
SERIES_MIN_CONSECUTIVE_YEARS = 8
SERIES_MIN_WORKS_PER_YEAR = 20
ID_CHECKS = ("Each candidate's OpenAlex id must be unique (no second OpenAlex institution with the same ROR), "
             "have a ROR id, and the ROR record must be active; ambiguous or ROR-less candidates are rejected "
             "with the reason recorded. Every candidate gets a row in the selection table (selected or the "
             "reason for rejection); none is dropped silently.")
DATA_RULES = ("Same as stage 2: retracted works and paratext excluded; publication years 2010-2025; authors "
              "counted only if affiliated with the university (institution or its lineage); the extraction "
              "date is stored because OpenAlex changes retroactively.")

# ── 2. Targets and criterion C1 (vs naive) ─────────────────────────────────────────────────────

MAIN_TARGETS = {
    "works_count": {"kind": "count"},
    "unique_authors": {"kind": "count"},
    "citations_received_in_year": {"kind": "count", "min_year": 2012},
    "intl_collab_share": {"kind": "share"},
    "top10_share": {"kind": "share"},
}
INTL_TARGETS = {  # new international module (counts, log growth)
    "n_partner_countries": {"kind": "count", "definition": "number of distinct countries of co-authors in the "
                                                             "year's works, excluding the university's own country"},
    "n_intl_works": {"kind": "count", "definition": "works with co-authors from >= 2 countries"},
    "n_partner_institutions": {"kind": "count", "definition": "distinct co-author institutions in the year's "
                                                                "works, excluding the university and its lineage"},
}
TARGETS = {**MAIN_TARGETS, **INTL_TARGETS}
SCALE = "counts: |log(yhat / y)| of the year-on-year log ratio; shares: |yhat - y|"
C1 = ("Criterion C1 = stage-2 SUCCESS_RULE against naive: relative MAE gain >= 10% and the 95% bootstrap CI "
      "(10 000 resamples of universities) of mean_u[MAE_u(model) - MAE_u(baseline)] entirely below 0, in BOTH "
      "rolling-origin and leave-one-university-out.")
PRIMARY_MODEL = {  # pre-declared model whose result decides each target (stage-2 best ML model; lgbm for new ones)
    "works_count": "lgbm", "unique_authors": "lgbm", "citations_received_in_year": "lgbm",
    "intl_collab_share": "ridge", "top10_share": "ridge",
    "n_partner_countries": "lgbm", "n_intl_works": "lgbm", "n_partner_institutions": "lgbm",
}
SECONDARY = "All other models are reported for every target; a pass by a non-primary model is exploratory."

# ── 3. Criterion C2 (vs mean growth) ───────────────────────────────────────────────────────────

AGE_GROUPS = {"1-3": (1, 3), "4-6": (4, 6), "7+": (7, 99)}
AGE_RULE = ("Series age in year t = t - first year with >= 10 works (stage-2 SERIES_START_MIN_WORKS) + 1.")
C2 = ("Criterion C2: the same rule as C1 with two baselines instead of naive: (a) panel mean growth = mean of "
      "all training target changes (constant from the training part), (b) mean growth of the series' age group "
      "(1-3, 4-6, 7+ years) in the training part (falls back to the panel mean if the group has < 5 training "
      "points). C2 passes only if the primary model beats BOTH baselines in BOTH schemes.")

# ── 4. Hypothesis for the international module ─────────────────────────────────────────────────

HYPOTHESIS_INTL = ("H-intl: the international counts (n_partner_countries, n_intl_works, n_partner_institutions) "
                   "are forecast better than naive, like works_count in stage 2: C1 holds for each; C2 is "
                   "reported. The hypothesis is supported for a target only if its primary model passes C1.")

# ── 5. Power (src/research/power_stage3.py -> results/research/stage3/power.csv, computed before models) ─

POWER_METHOD = ("d_u = MAE_u(primary) - MAE_u(naive) from stage-2 per-university metrics; CI half-width = "
                "1.96 sd(d)/sqrt(n); MDE(80% power) = 2.8 sd(d)/sqrt(n)/mean MAE(naive); detectable = max(10%, MDE). "
                "New international counts: naive MAE from the saved works of 13 universities, sd/MAE ratio "
                "assumed equal to works_count; n_partner_institutions uses n_intl_works as proxy.")
POWER_MDE80 = {  # relative gain detectable with 80% power, rolling / LOUO
    "works_count": {13: (0.369, 0.374), 40: (0.210, 0.213), 50: (0.188, 0.191), 60: (0.172, 0.174)},
    "unique_authors": {13: (0.365, 0.378), 40: (0.208, 0.215), 50: (0.186, 0.193), 60: (0.170, 0.176)},
    "citations_received_in_year": {13: (0.324, 0.332), 40: (0.185, 0.189), 50: (0.165, 0.169), 60: (0.151, 0.155)},
    "intl_collab_share": {13: (0.153, 0.138), 40: (0.087, 0.078), 50: (0.078, 0.070), 60: (0.071, 0.064)},
    "top10_share": {13: (0.132, 0.176), 40: (0.075, 0.101), 50: (0.067, 0.090), 60: (0.061, 0.082)},
    "n_partner_countries": {13: (0.369, 0.374), 40: (0.210, 0.213), 50: (0.188, 0.191), 60: (0.172, 0.174)},
    "n_intl_works": {13: (0.369, 0.374), 40: (0.210, 0.213), 50: (0.188, 0.191), 60: (0.172, 0.174)},
    "n_partner_institutions": {13: (0.369, 0.374), 40: (0.210, 0.213), 50: (0.188, 0.191), 60: (0.172, 0.174)},
}

AMENDMENT_1 = ("2026-10-19, before any stage-3 model: the first version described naive as 'last observed growth', "
               "contradicting C1 (= the stage-2 rule against the stage-2 naive, i.e. no change). Corrected to the "
               "stage-2 naive; the power analysis of the new international counts used the same wrong naive and was "
               "recomputed (relative detectable gains unchanged, absolute naive MAE changed).")

# ── 6. Models and evaluation ────────────────────────────────────────────────────────────────────

MODELS = ("naive", "drift3", "panel_mean", "age_mean", "ridge", "lgbm")
MODEL_RULES = {
    "naive": "stage-2 naive: next value = last observed value (growth 0), as in stage2.fit_predict",
    "drift3": "next growth = mean growth of the last 3 years of the series",
    "panel_mean": "next growth = mean target change of all training rows",
    "age_mean": "next growth = mean target change of training rows in the same age group",
    "ridge": "stage-2 features and grid (RIDGE_GRID), tuned inside the training part only",
    "lgbm": "stage-2 shallow LightGBM (LGBM_FIXED, LGBM_GRID), tuned inside the training part only",
}
NO_MODELS = "No neural networks, no Prophet."
SCHEMES = ("rolling", "louo")
EVALUATION = ("Stage-2 protocol: origins 2018-2024 (EVAL_ORIGINS), target year = origin + 1, calibration "
              "origins 2014-2017, inner validation on the last INNER_VALIDATION_ORIGINS training years. Run on the "
              "extended panel and, for comparison, on the 13 stage-2 universities. Metrics: MAE, MASE, bootstrap "
              "CI by university, share of universities where the model beats the baseline; per-university tables.")
CONFORMAL = ("Normalized split conformal: residuals divided by the university's historical volatility (sd of "
             "its growth in years <= origin, >= 3 values, floored at the 5th percentile); 80% level; "
             "empirical coverage by size tercile (median works_count over the panel years).")
SHAP = "TreeSHAP for the primary model of each target refitted at the last origin."
AITU = ("AITU forecast for 2026 only for targets whose primary model passes C1 (otherwise 'прогноз не строится'); "
        "percentile of AITU among panel universities for works, citations per author, intl collab share and "
        "partner countries — descriptive benchmark, not causality. No what-if scenarios, no hiring advice.")
