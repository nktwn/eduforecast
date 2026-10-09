import json
from functools import lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator

CONTRACT_VERSION = "finance-forecast/0.1.0"
SCHEMA_PATH = Path(__file__).with_name("forecast_response.schema.json")

TARGET_META = {
    "retention_rate": {"label": "Retention первокурсников", "unit": "%", "change_scale": "percentage_points"},
    "grad_rate_150": {"label": "Выпускаемость за 150% срока", "unit": "%", "change_scale": "percentage_points"},
    "fall_enrollment": {"label": "Осенний приём (численность)", "unit": "студентов", "change_scale": "log_ratio"},
    "core_total_per_fte_real": {"label": "Core-расходы на FTE", "unit": "$ FY2023 на FTE",
                                "change_scale": "log_ratio"},
}

FLAGS = {
    "MOCK_DATA": ("critical", "Синтетические данные мок-провайдера, не реальные значения"),
    "DEMO_MODEL": ("warning", "Демо-модель: обучена на годах до 2019, по критерию успеха не оценивалась"),
    "COVID_YEAR": ("info", "Год COVID (2020–2022): значения и изменения нетипичны"),
    "GASB75_2018": ("info", "2018: государственный вуз перешёл на GASB 75 (OPEB) — скачок в расходах"),
    "ID_TRANSITION": ("warning", "Смена UNITID или отчётной структуры: изменение за этот год не сопоставимо"),
    "MERGER_ABSORPTION": ("warning", "В этом году вуз поглотил другой вуз"),
    "NOT_ELIGIBLE": ("warning", "Показатель не прогнозируется: нет бакалавриата или когорта меньше 30"),
    "SMALL_COHORT": ("info", "Когорта меньше 30 студентов: значение шумное"),
    "FINANCE_PARENT_CHILD": ("info", "Финансы включают дочерние кампусы; FTE дочерних добавлен к знаменателю"),
    "FINANCE_PARTIAL": ("warning", "Частичная финансовая отчётность (часть данных у головной организации)"),
    "MISSING_VALUE": ("info", "Значение за год отсутствует"),
    "OUTLIER_CHANGE": ("warning", "Аномальное изменение за год"),
    "SHORT_HISTORY": ("warning", "Короткая история ряда (меньше 5 лет)"),
}


def flag(code: str, year: int | None = None, target: str | None = None, message: str | None = None) -> dict:
    severity, default = FLAGS[code]
    return {"code": code, "severity": severity, "message": message or default, "year": year, "target": target}


@lru_cache(maxsize=1)
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validate(response: dict) -> list[str]:
    validator = Draft202012Validator(schema())
    return [f"{'/'.join(map(str, e.absolute_path))}: {e.message}" for e in validator.iter_errors(response)]
