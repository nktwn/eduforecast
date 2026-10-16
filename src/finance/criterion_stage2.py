"""Pre-registration for Finance stages 3-4, committed BEFORE any model or regression is run.

The F1 success criterion (src/finance/criterion.py, commit 5b7e141) is imported, never changed.
Everything below fixes in advance: targets, sample, feature sets, models, hyper-parameter
grid and its nested selection, evaluation designs, intervals, explainability, and the
stage-4 hypotheses with their specification, multiple-testing correction and placebo.
"""
from src.finance.criterion import (  # noqa: F401  (re-exported: the criterion is the F1 one)
    BOOTSTRAP_SAMPLES,
    EVAL_ORIGINS,
    EVAL_SCOPES,
    RANDOM_SEED,
    SUCCESS_CI_LEVEL,
    SUCCESS_MIN_RELATIVE_MAE_GAIN,
    SUCCESS_RULE,
    TARGETS,
)

# ── Stage 3: forecasting models ────────────────────────────────────────────────────────

TARGET_LIST = list(TARGETS)  # retention_rate, grad_rate_150, fall_enrollment, core_total_per_fte_real

PREDICTION = (
    "Each model predicts the next-year change of the target on the criterion scale (percentage points "
    "for retention/graduation, log ratio for enrollment and real core expenses per FTE) from features "
    "observed in year t; the forecast is z_t + predicted change. Error = |forecast - actual| as in the "
    "criterion."
)
EVALUATION_SET = (
    "Exactly the prediction points of the F1 baseline (src/finance/baseline.py::predictions): same series, "
    "target years 2015-2023 (origins 2014-2022), same eligibility, splice and flag rules. Naive MAE is "
    "therefore identical to the F1 criterion table. A model must predict every point; missing feature "
    "values are imputed (Ridge: training medians plus missing-indicators are NOT used, only medians) or "
    "left to the model (LightGBM native missing handling)."
)
TRAINING_RULE = (
    "For origin o the model is fitted on all rows whose target year is <= o (features of year <= o-1) and "
    "predicts target year o+1 from features of year o. Flagged (COVID, GASB75, ID transition) target "
    "years stay in training; ID-transition and merger target years are excluded from training targets "
    "exactly as from evaluation. Features are standardized/winsorized with statistics of the training "
    "part only (winsorization at the 1st and 99th percentiles, Ridge only)."
)

# Feature sets (names refer to columns built in src/finance/models_stage2.py from panel_stage2).
S1 = [
    # target lags (on the target scale)
    "target_level", "target_change_1", "target_change_2", "target_change_3",
    # size
    "log_fte", "log_enrollment",
    # sector and Carnegie
    "control_public", "carnegie",
]
S2_EXTRA = [
    # function shares of the 6 operating functions (scholarships excluded: GASB/FASB incomparable)
    "instruction_share_ops", "research_share_ops", "public_service_share_ops", "academic_support_share_ops",
    "student_services_share_ops", "institutional_support_share_ops",
    # their lag 1
    "instruction_share_ops_lag1", "research_share_ops_lag1", "public_service_share_ops_lag1",
    "academic_support_share_ops_lag1", "student_services_share_ops_lag1", "institutional_support_share_ops_lag1",
    # per FTE, real FY2023 dollars (log)
    "log_core_real", "log_instruction_real", "log_student_services_real", "log_academic_support_real",
    "log_institutional_support_real",
    # real core growth t-1->t and t-2->t-1
    "core_real_growth_1", "core_real_growth_2",
    # natural classes
    "nat_compensation_share", "nat_depreciation_share", "nat_interest_share",
    # gross scholarships share (harmonized)
    "sch_gross_share",
]
S3_EXTRA = [
    # selectivity
    "admit_rate", "yield_rate",
    # Pell, price, aid
    "pell_share_ug", "log_net_price_real", "log_tuition_instate_real", "inst_aid_share_ftft",
    # staff
    "log_faculty_salary_real", "ft_instr_staff_share", "fte_per_faculty",
    # enrollment mix
    "full_time_share", "graduate_share",
    # programme mix
    "deg_share_stem", "deg_share_computer_science", "deg_share_engineering", "deg_share_health",
    "deg_share_business", "deg_share_education", "deg_share_humanities_arts", "deg_share_social_behavioral",
]
FEATURE_SETS = {"S1": S1, "S2": S1 + S2_EXTRA, "S3": S1 + S2_EXTRA + S3_EXTRA}

MODELS = {
    "constant": "Ridge with intercept only = mean next-year change of all training rows (panel mean growth)",
    "ridge": "Ridge regression (L2 loss), Carnegie one-hot, median imputation, train-only winsorization 1/99 "
             "and standardization",
    "lgbm": "LightGBM, L1 loss (the criterion is MAE), shallow trees, strong regularization, native NaN, "
            "Carnegie as integer code",
}
PRIMARY = ("lgbm", "S3")  # the pre-declared main model per target; all others are reported as ablation

RIDGE_ALPHAS = [0.1, 1.0, 10.0, 100.0, 1000.0]
LGBM_FIXED = {
    "objective": "regression_l1", "learning_rate": 0.03, "subsample": 0.8, "subsample_freq": 1,
    "colsample_bytree": 0.8, "reg_lambda": 10.0, "max_depth": 4, "random_state": RANDOM_SEED, "verbose": -1,
    "n_jobs": 4,
}
LGBM_GRID = {"num_leaves": [4, 8], "min_child_samples": [50, 200], "n_estimators": [150, 400]}
NESTED_SELECTION = (
    "Hyper-parameters are chosen inside the training part only: for origin o, candidates are fitted on "
    "target years <= o-1 and scored by MAE on target year o (the last training year); the winner is refitted "
    "on all target years <= o. Test years are never used for selection."
)

UNSEEN = {
    "origins": [2016, 2019, 2022],
    "holdout_share": 0.20,
    "n_splits": 5,
    "split_seeds": [0, 1, 2, 3, 4],
    "rule": "For each split, 20% of the target's series_ids (drawn among series present in the evaluation set) "
            "are removed from training entirely, at all years; models are fitted on the remaining 80% with "
            "target years <= o and evaluated on the held-out series at target year o+1 (same points as the "
            "rolling evaluation restricted to those series and origins). The success rule is applied per split "
            "(per-institution MAE averaged over the 3 origins, bootstrap over held-out institutions) and in both "
            "scopes; the unseen check passes if it holds in all 5 splits.",
}
BREAKDOWNS = ("control_label", "size_tercile", "carnegie_group")
SIZE_TERCILE_RULE = "Terciles of the series' median log FTE over 2010-2023, computed once on all series."

# Intervals (primary model only)
INTERVAL_LEVEL = 0.80
INTERVAL_RULE = (
    "Split conformal normalized by the series' historical volatility. For origin o, a calibration model is "
    "fitted on target years <= o-1 and predicts target year o; scores s = |y - yhat| / sigma_i, where "
    "sigma_i is the standard deviation of the series' target changes in years <= o-1 (at least 3 changes; "
    "otherwise the median sigma of the calibration rows), floored at the 5th percentile of sigma. "
    "q = the ceil((n+1)*0.8)/n empirical quantile of s. Interval for target year o+1: forecast +- q * sigma_i "
    "(sigma_i now from years <= o). Coverage is reported overall, by sector, by size tercile and for COVID "
    "target years (2020-2022) vs other years."
)

EXPLAIN = (
    "TreeSHAP (LightGBM pred_contrib) of the primary model refitted at the last origin (2022); mean |SHAP| "
    "per feature and one institution example in the existing JSON contract (src/finance/api). Ridge: "
    "standardized coefficients of the S3 model at origin 2022."
)

# ── Stage 4: budget structure -> outcomes (association, not effect) ────────────────────

SHARE_DENOMINATOR = (
    "Function share = function expense / sum of the 6 operating functions (instruction, research, public "
    "service, academic support, student services, institutional support), in percentage points (0-100). "
    "Scholarships are excluded from the denominator because GASB and FASB report them incomparably."
)
HYPOTHESES = {
    "H1": {"share": "student_services", "outcome": "retention_rate", "expected_sign": +1, "window": "same_year"},
    "H2": {"share": "instruction", "outcome": "grad_rate_150", "expected_sign": +1, "window": "cohort_t-5_t"},
    "H3": {"share": "academic_support", "outcome": "retention_rate", "expected_sign": +1, "window": "same_year"},
    "H4": {"share": "institutional_support", "outcome": "grad_rate_150", "expected_sign": -1,
           "window": "cohort_t-5_t"},
}
FE_SPEC = (
    "Delta y_it = beta * Delta share_it + alpha_i + gamma_t + e_it, first differences between consecutive years "
    "of the same series_id, two-way fixed effects (series_id and year) by alternating demeaning, standard "
    "errors clustered by series_id (CR1: G/(G-1) * (N-1)/(N-K)). Outcomes in percentage points; eligibility "
    "as in the criterion (retention: eligible_retention; graduation: eligible_grad) in both years; ID-transition "
    "and merger years dropped; superseded rows dropped. For retention, Delta share is the same fiscal year t "
    "(FY July t-1 - June t covers the cohort's first year). For graduation, the share is the mean over FY "
    "t-5..t (all 6 years required) and Delta is its change from t-1 to t. Main specification: both Delta "
    "variables winsorized at the 1st/99th percentiles of the estimation sample; no other controls."
)
SENSITIVITY = {
    "lag1": "Delta share of year t-1 instead of t",
    "no_covid": "drop outcome years 2020-2022",
    "public_only": "control == 1",
    "private_only": "control == 2",
    "no_winsorize": "main specification without winsorization",
    "with_controls": "adds Delta log FTE and Delta log real core expenses per FTE",
}
PLACEBO = (
    "Lead test: Delta y_t on Delta share_{t+1} (next year's change; for graduation the window t-4..t+1), same "
    "FE and clustering. A lead coefficient with unadjusted p < 0.05 is recorded as a sign of confounding or "
    "reverse causation for that hypothesis."
)
ALPHA = 0.05
MULTIPLE_TESTING = (
    "Holm-Bonferroni over the 4 main-specification tests (two-sided p-values). A hypothesis is called "
    "'association supported' only if the Holm-adjusted p < 0.05 AND the sign matches the expected sign; "
    "a significant opposite sign is reported as 'association in the opposite direction'. Sensitivity and "
    "placebo results are reported with raw p-values (and Holm within each family). Results are described as "
    "associations, never as effects."
)
