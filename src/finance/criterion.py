from src.finance.config import YEAR_MAX

TARGETS = {
    "retention_rate": {"kind": "level", "unit": "percentage points"},
    "grad_rate_150": {"kind": "level", "unit": "percentage points"},
    "fall_enrollment": {"kind": "log", "unit": "log growth"},
    "total_per_fte": {"kind": "log", "unit": "log growth"},
}

BASELINE = "naive"
EVAL_ORIGINS = list(range(2014, YEAR_MAX))
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
    "rates and |log(yhat / y)| for enrollment and expenses per FTE. Rolling origin, horizon 1 year, "
    "origins 2014-2022, same institutions and years for model and naive."
)
