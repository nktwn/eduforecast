from src.finance.config import YEAR_MAX

TARGETS = {
    "retention_rate": {"kind": "level", "unit": "percentage points", "eligibility": "eligible_retention"},
    "grad_rate_150": {"kind": "level", "unit": "percentage points", "eligibility": "eligible_grad"},
    "fall_enrollment": {"kind": "log", "unit": "log growth", "eligibility": None},
    "core_total_per_fte_real": {"kind": "log", "unit": "log growth", "eligibility": None},
}

PRICE_INDEX = "CPI-U, all items, not seasonally adjusted (FRED CPIAUCNS), fiscal-year average July-June"
PRICE_BASE_FY = YEAR_MAX
MIN_COHORT = 30
ELIGIBILITY_RULE = (
    "Retention and 150% graduation rate are modelled only for institutions that report a bachelor's "
    "degree-seeking GRS subcohort (GRTYPE 8) in at least one year, and only in years where the relevant "
    "cohort (RRFTCTA for retention, GRTYPE 8 adjusted cohort for graduation) is at least 30 students."
)

COVID_TARGET_YEARS = (2020, 2021, 2022)
GASB75_PUBLIC_TARGET_YEAR = 2018
FLAG_RULE = (
    "A prediction is flagged if its target year is 2020-2022 (COVID), or it is a public institution "
    "with target year 2018 (GASB 75 OPEB adoption), or the institution changed UNITID in the target "
    "year (spliced reporting change). Every evaluation is reported twice: all years, and excluding "
    "flagged predictions."
)
SPLICE_RULE = (
    "If an institution leaves the panel with NEWID pointing to a successor whose first panel year is "
    "the next year, it is a reporting/ID change: the two series are spliced under one series_id and the "
    "transition year is flagged (its growth is excluded from evaluation). If the successor already "
    "existed in the panel, it is a real merger: the absorbed series ends and is not spliced."
)

BASELINE = "naive"
EVAL_ORIGINS = list(range(2014, YEAR_MAX))
EVAL_SCOPES = ("all_years", "excluding_flagged")
GROUP_COLUMN = "peer_group"
GROUP_MIN_SIZE = 5
GROUP_CHANGE_CLIP = {"level": 20.0, "log": 1.0}

SUCCESS_MIN_RELATIVE_MAE_GAIN = 0.10
SUCCESS_CI_LEVEL = 0.95
BOOTSTRAP_SAMPLES = 2000
RANDOM_SEED = 42
SUCCESS_RULE = (
    "A future model beats naive on a target if (a) its MAE is at least 10% lower than naive MAE, "
    "1 - mean_i MAE_i(model) / mean_i MAE_i(naive) >= 0.10, and (b) the 95% bootstrap CI "
    "(resampling institutions with replacement) of mean_i [MAE_i(model) - MAE_i(naive)] lies "
    "entirely below 0. Errors are |yhat - y| in percentage points for retention and graduation "
    "rates and |log(yhat / y)| for enrollment and real core expenses per FTE. Rolling origin, horizon "
    "1 year, origins 2014-2022, same institutions and years for model and naive, eligibility rules "
    "applied. The rule must hold in both evaluation scopes (all years and excluding flagged)."
)
