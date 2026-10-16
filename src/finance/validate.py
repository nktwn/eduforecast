"""Type and range checks for the stage-2 finance panel, outlier rules, data dictionary.

SCHEMA is the single source for both the checks and data/finance/DATA_DICTIONARY.md.

  python -m src.finance.validate          # checks panel_stage2.parquet, writes the dictionary
"""
import numpy as np
import pandas as pd

from src.finance.config import FINANCE_DATA_DIR, FINANCE_RESULTS_DIR, YEAR_MAX, YEAR_MIN

DICTIONARY_PATH = FINANCE_DATA_DIR / "DATA_DICTIONARY.md"
VALIDATION_PATH = FINANCE_RESULTS_DIR / "stage2_validation.csv"
MISSINGNESS_PATH = FINANCE_RESULTS_DIR / "stage2_missingness.csv"

ALL = f"{YEAR_MIN}–{YEAR_MAX}"
SHARE = {"dtype": "float", "min": 0.0, "max": 1.0, "unit": "доля 0–1"}
MONEY = {"dtype": "float", "min": 0.0, "max": None, "unit": "$"}
REAL = {"dtype": "float", "min": 0.0, "max": None, "unit": "$ FY2023 (CPI-U)"}
COUNT = {"dtype": "float", "min": 0.0, "max": None, "unit": "человек"}
# Accounting shares can leave [0, 1] legitimately (e.g. negative GASB 68/75 benefit expense);
# hard bounds catch parsing errors, values outside [0, 1] are an outlier rule.
ACC = {"min": -1.0, "max": 2.0}


def _s(meaning, source, years=ALL, component=None, **kw):
    spec = {**SHARE, **kw} if "unit" not in kw and "dtype" not in kw else kw
    return {"meaning": meaning, "source": source, "years": years, "component": component, **spec}


def _m(meaning, source, base=MONEY, years=ALL, component=None, **kw):
    return {"meaning": meaning, "source": source, "years": years, "component": component, **base, **kw}


ADM_SRC = "IC{Y} (2010–2013) / ADM{Y} (2014–2023): APPLCN, ADMSSN, ENRLT"
SCHEMA = {
    # keys
    "unitid": {"meaning": "Идентификатор вуза IPEDS", "source": "HD{Y}", "years": ALL, "component": "keys",
               "dtype": "int", "min": 100000, "max": 999999, "unit": "код"},
    "year": {"meaning": "Год сбора IPEDS (см. FINANCE_DATA_AUDIT.md §1)", "source": "—", "years": ALL,
             "component": "keys", "dtype": "int", "min": YEAR_MIN, "max": YEAR_MAX, "unit": "год"},
    # F1 targets (for range checks)
    "retention_rate": {"meaning": "Retention очных первокурсников (цель)", "source": "EF{Y}D RET_PCF", "years": ALL,
                       "component": "F1", "dtype": "float", "min": 0, "max": 100, "unit": "%"},
    "grad_rate_150": {"meaning": "Выпускаемость бакалавров за 150% срока (цель)", "source": "GR{Y}", "years": ALL,
                      "component": "F1", "dtype": "float", "min": 0, "max": 100, "unit": "%"},
    "fall_enrollment": _m("Осенний приём, все студенты (цель)", "EF{Y}A EFTOTLT", COUNT, component="F1"),
    "core_total_per_fte_real": _m("Core-расходы (7 категорий) на FTE (цель)", "F1A/F2 + EFIA", REAL, component="F1"),
    # ADM
    "applicants": _m("Заявки первокурсников", ADM_SRC, COUNT, component="ADM"),
    "admitted": _m("Принятые", ADM_SRC, COUNT, component="ADM"),
    "enrolled_first_time": _m("Зачисленные первокурсники", ADM_SRC, COUNT, component="ADM"),
    "admit_rate": _s("Доля принятых = admitted / applicants", ADM_SRC, component="ADM"),
    "yield_rate": _s("Yield = enrolled / admitted", ADM_SRC, component="ADM"),
    # SFA
    "pell_share_ug": _s("Доля бакалавров с грантом Pell", "SFA{Y-1}{Y} UPGRNTP / 100", component="SFA"),
    "pell_share_ftft": _s("Доля очных первокурсников с Pell", "SFA{Y-1}{Y} PGRNT_P / 100", component="SFA"),
    "inst_aid_share_ftft": _s("Доля очных первокурсников с институциональной помощью", "SFA{Y-1}{Y} IGRNT_P / 100",
                              component="SFA"),
    "net_price": _m("Средняя чистая цена для получателей грантов (публичные — для жителей штата)",
                    "SFA{Y-1}{Y} NPIST2 (публичные) / NPGRN2 (частные)", component="SFA", min=None),
    "net_price_real": _m("То же в $ FY2023", "производный", REAL, component="SFA", min=None),
    # IC
    "tuition_fees_instate": _m("Опубликованная плата за обучение и сборы, для жителей штата", "IC{Y}_AY CHG2AY3",
                               component="IC"),
    "tuition_fees_outstate": _m("То же, для нерезидентов штата", "IC{Y}_AY CHG3AY3", component="IC"),
    "room_board_oncampus": _m("Проживание и питание в кампусе", "IC{Y}_AY CHG5AY3", component="IC"),
    "tuition_fees_instate_real": _m("Плата за обучение (резиденты), $ FY2023", "производный", REAL, component="IC"),
    # staff
    "faculty_avg_salary_9mo": _m("Средняя зарплата штатных преподавателей, приведённая к 9 месяцам, все ранги",
                                 "SAL{Y}_IS: SAEQ9AT (2016–2023), 9 × SAAVMNT (2012–2015); ARANK 7",
                                 years="2012–2023", component="SAL", max=400000),
    "faculty_avg_salary_9mo_real": _m("То же в $ FY2023", "производный", REAL, years="2012–2023",
                                      component="SAL", max=500000),
    "ft_instr_staff_share": _s("Доля штатных (full-time) среди преподавательского персонала",
                               "EAP{Y} EAPFT / EAPTOT (EAPCAT 21000)", years="2012–2023", component="EAP"),
    # EF mix
    "full_time_share": _s("Доля очных студентов", "EF{Y}A EFALEVEL 21 / 1", component="EF"),
    "part_time_share": _s("Доля заочных (part-time) студентов", "EF{Y}A EFALEVEL 41 / 1", component="EF"),
    "graduate_share": _s("Доля магистрантов и аспирантов", "EF{Y}A EFALEVEL 12 / 1", component="EF"),
    # completions
    "bachelor_degrees": _m("Степени бакалавра, первая специальность", "C{Y}_A AWLEVEL 5, MAJORNUM 1, CIP 6 знаков",
                           COUNT, component="C"),
    **{f"deg_share_{g}": _s(f"Доля бакалаврских степеней: {g} (CIP2 {codes})", "C{Y}_A", component="C")
       for g, codes in {"stem": "11,14,15,26,27,40,41", "computer_science": "11", "engineering": "14,15",
                        "math_physical_bio": "26,27,40,41", "health": "51", "business": "52",
                        "education": "13", "law": "22", "social_behavioral": "42,45",
                        "humanities_arts": "16,23,24,38,50,54"}.items()},
    # natural classes
    "nat_salaries_share": _s("Доля зарплат в итоге расходов", "F1A F1C192 / F2 F2E132", component="F natural", **ACC),
    "nat_benefits_share": _s("Доля льгот (benefits)", "F1A F1C193 / F2 F2E133", component="F natural", **ACC),
    "nat_om_share": _s("Доля эксплуатации зданий (O&M) как натуральной статьи",
                       "F1A F1C19OM / F2 F2E134", years="2016–2023 (до FY2016 обе формы дают 0: O&M "
                       "распределён по другим статьям)", component="F natural", **ACC),
    "nat_depreciation_share": _s("Доля амортизации", "F1A F1C19DP|F1C194 / F2 F2E135", component="F natural", **ACC),
    "nat_interest_share": _s("Доля процентов", "F1A F1C19IN|F1C197 / F2 F2E136", component="F natural", **ACC),
    "nat_other_incl_om_share": _s("Доля прочих расходов вместе с O&M (сопоставимо во все годы)",
                                  "F1A F1C19OT|F1C195 + O&M / F2 F2E137 + F2E134", component="F natural", **ACC),
    "nat_compensation_share": _s("Доля оплаты труда (зарплаты + льготы)", "производный", component="F natural", **ACC),
    "nat_salaries_per_fte_real": _m("Зарплаты на FTE, $ FY2023", "производный", REAL, component="F natural"),
    "nat_depreciation_per_fte_real": _m("Амортизация на FTE, $ FY2023", "производный", REAL, component="F natural"),
    **{f"{c}_share_core": _s(f"Доля функции «{c}» в core-расходах (7 категорий)", "F1A часть C / F2 часть E",
                              component="F functions", **ACC)
       for c in ("instruction", "research", "public_service", "academic_support", "student_services",
                 "institutional_support", "scholarships")},
    "core_share_of_total": _s("Доля core-расходов (7 категорий) в итоге расходов", "производный",
                              component="F functions", **ACC),
}

# Outlier rules: flagged, never silently removed (FINANCE_DATA_AUDIT.md §15).
OUTLIER_RULES = {
    "admit_rate_tiny_pool": ("admit_rate == 1 при менее чем 50 заявках",
                             lambda p: (p["admit_rate"] >= 1) & (p["applicants"] < 50)),
    "yield_above_one": ("yield > 1: зачислено больше, чем принято",
                        lambda p: p["yield_rate"] > 1),
    "natural_classes_do_not_sum": ("сумма натуральных статей отличается от итога больше чем на 1%",
                                   lambda p: (p[["nat_salaries", "nat_benefits", "nat_depreciation", "nat_interest",
                                                 "nat_other_incl_om"]].sum(axis=1, min_count=5)
                                              / p["nat_total"] - 1).abs() > 0.01),
    "degree_shares_above_one": ("сумма долей областей больше 1",
                                lambda p: p[[f"deg_share_{g}" for g in ("computer_science", "engineering",
                                                                         "math_physical_bio", "health", "business",
                                                                         "education", "law", "social_behavioral",
                                                                         "humanities_arts")]].sum(axis=1) > 1.0001),
    "salary_extreme": ("зарплата (9 мес.) вне 0.5–99.5 перцентиля года",
                       lambda p: _outside_pct(p, "faculty_avg_salary_9mo_real")),
    "accounting_share_outside_0_1": ("доля натуральной статьи или core-доля вне [0; 1] (отрицательные начисления, "
                                     "системные офисы)",
                                     lambda p: ((p[[f"nat_{c}_share" for c in ("salaries", "benefits", "depreciation",
                                                                                "interest")]] < 0)
                                                | (p[[f"nat_{c}_share" for c in ("salaries", "benefits",
                                                                                  "depreciation", "interest")]] > 1)
                                                ).any(axis=1) | (p["core_share_of_total"] > 1)),
    "system_office": ("системный офис или администрация, а не кампус (название)",
                      lambda p: p["name"].str.contains(SYSTEM_OFFICE_PATTERN, case=False, regex=True)),
    "net_price_extreme": ("чистая цена вне 0.5–99.5 перцентиля года",
                          lambda p: _outside_pct(p, "net_price_real")),
    "salaries_per_fte_extreme": ("зарплаты на FTE вне 0.5–99.5 перцентиля года",
                                 lambda p: _outside_pct(p, "nat_salaries_per_fte_real")),
}


SYSTEM_OFFICE_PATTERN = (r"system office|central office|office of the chancellor|system administration|"
                         r"university administration|board of regents")


def _outside_pct(p: pd.DataFrame, col: str) -> pd.Series:
    lo = p.groupby("year")[col].transform(lambda s: s.quantile(0.005))
    hi = p.groupby("year")[col].transform(lambda s: s.quantile(0.995))
    return (p[col] < lo) | (p[col] > hi)


def check_schema(p: pd.DataFrame) -> pd.DataFrame:
    """One row per (column, rule) with violations; missing columns are errors."""
    rows = []
    for col, spec in SCHEMA.items():
        if col not in p.columns:
            rows.append({"column": col, "rule": "column_missing", "severity": "error", "n": len(p), "examples": ""})
            continue
        s = p[col]
        numeric = pd.to_numeric(s, errors="coerce")
        bad_type = s.notna() & numeric.isna()
        if spec["dtype"] == "int":
            bad_type |= numeric.notna() & (numeric != np.floor(numeric))
        for rule, mask in (("type", bad_type),
                           ("below_min", numeric < spec["min"] if spec.get("min") is not None else None),
                           ("above_max", numeric > spec["max"] if spec.get("max") is not None else None)):
            if mask is None or not mask.any():
                continue
            ex = p.loc[mask, ["unitid", "year", col]].head(3).to_dict("records")
            rows.append({"column": col, "rule": rule, "severity": "error", "n": int(mask.sum()), "examples": str(ex)})
    dup = p.duplicated(["unitid", "year"])
    if dup.any():
        rows.append({"column": "unitid,year", "rule": "duplicate_key", "severity": "error", "n": int(dup.sum()),
                     "examples": ""})
    return pd.DataFrame(rows, columns=["column", "rule", "severity", "n", "examples"])


def outliers(p: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for name, (desc, fn) in OUTLIER_RULES.items():
        mask = fn(p).fillna(False)
        rows.append({"column": name, "rule": desc, "severity": "warning", "n": int(mask.sum()),
                     "examples": str(p.loc[mask, ["unitid", "year"]].head(3).to_dict("records"))})
    return pd.DataFrame(rows)


def missingness(p: pd.DataFrame) -> pd.DataFrame:
    """Share of panel rows with a value, by component key column and year."""
    keys = {"ADM": "admit_rate", "SFA: Pell": "pell_share_ug", "SFA: net price": "net_price",
            "SFA: инст. помощь": "inst_aid_share_ftft", "IC: плата": "tuition_fees_instate",
            "IC: проживание": "room_board_oncampus", "SAL: зарплата": "faculty_avg_salary_9mo",
            "EAP: доля штатных": "ft_instr_staff_share", "EF: очные/магистранты": "graduate_share",
            "C: программы": "deg_share_stem", "F: натуральные статьи": "nat_salaries_share",
            "F: O&M отдельно": "nat_om_share"}
    out = pd.DataFrame({name: p.groupby("year")[col].apply(lambda s: s.notna().mean()) for name, col in keys.items()})
    return out.round(3)


def _coverage(p: pd.DataFrame, col: str) -> str:
    if p is None or col not in p.columns:
        return "—"
    share = p.groupby("year")[col].apply(lambda s: s.notna().mean())
    good = share[share >= 0.5].index
    span = f"{good.min()}–{good.max()}" if len(good) else "нет лет с ≥50%"
    return f"{span}; заполнено {p[col].notna().mean():.0%}"


def write_dictionary(p: pd.DataFrame | None = None, path=DICTIONARY_PATH) -> None:
    lines = ["# DATA_DICTIONARY.md — панель Finance, этап 2",
             "",
             "Файл генерируется из `src/finance/validate.py::SCHEMA` командой `python -m src.finance.validate`; "
             "правьте схему, а не этот файл.",
             "",
             "Панель: `data/finance/panel_stage2.parquet` = панель F1 (`panel.parquet`, описана в "
             "`FINANCE_DATA_AUDIT.md` §1–§14) + новые колонки, соединённые по (`unitid`, `year`). "
             "Год Y — год сбора IPEDS. Реальные деньги — CPI-U, среднее за финансовый год июль–июнь, база FY2023.",
             "",
             "Лаги: `<имя>_lag{k}` — значение того же ряда (`series_id`) ровно в году t−k, k = 1–3; "
             "если года нет, лаг пустой (`src/finance/features_stage2.py`).",
             "",
             "| имя | смысл | единицы | допустимый диапазон | источник | годы (по источнику) | покрытие в панели |",
             "|---|---|---|---|---|---|---|"]
    for col, s in SCHEMA.items():
        rng = f"[{'' if s.get('min') is None else s['min']}; {'' if s.get('max') is None else s['max']}]"
        lines.append(f"| `{col}` | {s['meaning']} | {s['unit']} | {rng} | {s['source']} | {s['years']} | "
                     f"{_coverage(p, col)} |")
    lines += ["", "## Правила выбросов", "",
              "Выбросы помечаются, а не удаляются. Модели этапа 3 видят их как есть; проверка устойчивости — "
              "в `FINANCE_STAGE2_REPORT.md`.", "", "| правило | условие |", "|---|---|"]
    lines += [f"| `{k}` | {v[0]} |" for k, v in OUTLIER_RULES.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    from src.finance.panel_stage2 import PANEL2_PATH

    p = pd.read_parquet(PANEL2_PATH)
    report = pd.concat([check_schema(p), outliers(p)], ignore_index=True)
    report.to_csv(VALIDATION_PATH, index=False)
    miss = missingness(p)
    miss.to_csv(MISSINGNESS_PATH)
    write_dictionary(p)
    pd.set_option("display.width", 250)
    print(report.drop(columns="examples").to_string(index=False))
    print(miss.to_string())


if __name__ == "__main__":
    main()
