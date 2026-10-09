from src.research.config import RESEARCH_RESULTS_DIR

STAGE2_DIR = RESEARCH_RESULTS_DIR / "stage2"
STAGE2_DIR.mkdir(parents=True, exist_ok=True)

RANDOM_SEED = 42

LAST_COMPLETE_YEAR = 2025
EVAL_ORIGINS = list(range(2018, 2025))
CALIBRATION_ORIGINS = list(range(2014, 2018))
QUALITY_MAIN_MAX_TARGET_YEAR = 2023

SERIES_START_MIN_WORKS = 10
N_GROWTH_LAGS = 3
INNER_VALIDATION_ORIGINS = 3

TARGETS = {
    "works_count": {"kind": "count", "role": "main"},
    "unique_authors": {"kind": "count", "role": "main"},
    "intl_collab_share": {"kind": "share", "role": "main"},
    "top10_share": {"kind": "share", "role": "main", "quality": True},
    "citations_received_in_year": {"kind": "count", "role": "main", "min_year": 2012},
    "citations_per_author": {"kind": "count", "role": "main", "min_year": 2012},
    "fwci_median": {"kind": "share", "role": "secondary", "quality": True},
    "unique_authors_no_hyper": {"kind": "count", "role": "secondary"},
}

MODELS = ("naive", "drift", "ridge", "lgbm")
BASELINE = "naive"

RIDGE_GRID = [{"alpha": a} for a in (0.1, 1.0, 10.0, 100.0, 1000.0)]
LGBM_GRID = [
    {"n_estimators": n, "min_child_samples": m, "reg_lambda": r}
    for n in (50, 150)
    for m in (10, 20)
    for r in (1.0, 10.0)
]
LGBM_FIXED = {
    "max_depth": 2,
    "num_leaves": 3,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "subsample_freq": 1,
    "colsample_bytree": 0.8,
    "verbose": -1,
}

SUCCESS_MIN_RELATIVE_MAE_GAIN = 0.10
SUCCESS_CI_LEVEL = 0.95
BOOTSTRAP_SAMPLES = 10_000
SUCCESS_RULE = (
    "Model beats naive on a target if (a) relative MAE gain on the growth scale, "
    "1 - mean_u MAE_u(model) / mean_u MAE_u(naive), is >= 10%, and (b) the 95% "
    "bootstrap CI (resampling universities) of mean_u [MAE_u(model) - MAE_u(naive)] "
    "lies entirely below 0. Growth scale: |log(yhat/y)| for counts, |yhat - y| for shares. "
    "Evaluated separately for the rolling-origin and leave-one-university-out schemes, "
    "on the main sample."
)

CONFORMAL_LEVELS = (0.8, 0.9)
CONFORMAL_MIN_RESIDUALS = 20

EXCLUDE_YEARS = {"SDU": range(2010, 2017)}
SDU_MAIN_INCLUDED = False
SDU_RULE = (
    "SDU 2017-2025 enters the main sample only after the authorship-level affiliation "
    "check: works whose SDU-linked authorships carry only Turkish markers (Isparta, "
    "Turkey/Turkiye, Universitesi) and no Kazakhstan markers must be <= 5% of SDU works "
    "over 2017-2025 and <= 10% in every year. Until the check runs, SDU is excluded "
    "from the main sample and included 2017-2025 as a sensitivity."
)
SDU_MAX_MISATTRIBUTED_TOTAL = 0.05
SDU_MAX_MISATTRIBUTED_YEAR = 0.10

FLAGGED_POINTS = {("KBTU", 2021)}
