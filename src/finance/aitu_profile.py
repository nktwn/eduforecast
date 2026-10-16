"""Structured financial profile of Astana IT University (data/aitu/).

Figures were read from a scanned 2020 financial statement (thousand KZT) and are
stored with verified=false. Two years only (2019 is the first full year of
operation, 2020 the second): structure can be described, trends cannot.

  python -m src.finance.aitu_profile
"""
import pandas as pd

from src.config import BASE_DIR

AITU_DIR = BASE_DIR / "data" / "aitu"
FINANCIALS_PATH = AITU_DIR / "financials_2019_2020.csv"
CHECK_TOLERANCE = 1.0  # thousand KZT; larger discrepancies are listed separately

CHECKS = {
    "revenue_by_source": (["revenue_services", "revenue_rent", "revenue_other"], ["revenue_total"]),
    "services_by_item": (["services_state_order", "services_paid_tuition", "services_research_project",
                          "services_english_courses"], ["revenue_services"]),
    "expenses_by_item": (["exp_payroll", "exp_social_contrib", "exp_taxes", "exp_travel", "exp_depreciation",
                          "exp_interest", "exp_utilities_property_tax_2019_2020", "exp_other"], ["exp_total"]),
    "assets_equal_liabilities_and_equity": (["bs_current_liabilities", "bs_noncurrent_liabilities", "bs_equity"],
                                            ["bs_total_assets"]),
    "revenue_minus_expenses_equals_operating_loss": (["revenue_total", "-exp_total"], ["loss_operating"]),
}


def load(path=FINANCIALS_PATH) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["verified"] = df["verified"].astype(str).str.lower().eq("true")
    return df


def _wide(df: pd.DataFrame) -> pd.DataFrame:
    return df.pivot_table(index="year", columns="indicator", values="value", aggfunc="first")


def _sum(row: pd.Series, items: list[str]) -> float | None:
    total = 0.0
    for item in items:
        sign, name = (-1, item[1:]) if item.startswith("-") else (1, item)
        if pd.isna(row.get(name)):
            return None
        total += sign * row[name]
    return total


def sum_checks(df: pd.DataFrame) -> pd.DataFrame:
    """Every check for every year where all its items are present."""
    rows = []
    for year, row in _wide(df).iterrows():
        for name, (parts, total) in CHECKS.items():
            lhs, rhs = _sum(row, parts), _sum(row, total)
            if lhs is None or rhs is None:
                continue
            diff = lhs - rhs
            rows.append({"year": int(year), "check": name, "sum_of_parts": lhs, "reported_total": rhs,
                         "difference": diff, "ok": abs(diff) <= CHECK_TOLERANCE})
    years = sorted(_wide(df).index)
    w = _wide(df)
    for prev, cur in zip(years, years[1:]):
        if {"bs_equity", "loss_period"} <= set(w.columns) and w.loc[[prev, cur], "bs_equity"].notna().all() \
                and pd.notna(w.at[cur, "loss_period"]):
            lhs = w.at[cur, "bs_equity"] - w.at[prev, "bs_equity"]
            diff = lhs - w.at[cur, "loss_period"]
            rows.append({"year": int(cur), "check": "equity_change_equals_period_loss", "sum_of_parts": lhs,
                         "reported_total": w.at[cur, "loss_period"], "difference": diff,
                         "ok": abs(diff) <= CHECK_TOLERANCE})
    return pd.DataFrame(rows)


def structure(df: pd.DataFrame) -> pd.DataFrame:
    """Structural ratios per year (only where the inputs exist)."""
    w = _wide(df)
    out = pd.DataFrame(index=w.index)

    def col(name):
        return w[name] if name in w else pd.Series(float("nan"), index=w.index)

    rev = col("revenue_total")
    out["share_revenue_services"] = col("revenue_services") / rev
    out["share_revenue_rent"] = col("revenue_rent") / rev
    out["share_revenue_other"] = col("revenue_other") / rev
    out["share_state_order_in_revenue"] = col("services_state_order") / rev
    out["share_paid_tuition_in_revenue"] = col("services_paid_tuition") / rev
    out["share_research_in_revenue"] = col("services_research_project") / rev
    out["share_payroll_with_social_in_expenses"] = (col("exp_payroll") + col("exp_social_contrib")) / col("exp_total")
    out["share_depreciation_in_expenses"] = col("exp_depreciation") / col("exp_total")
    out["share_interest_in_expenses"] = col("exp_interest") / col("exp_total")
    out["current_ratio"] = col("bs_current_assets") / col("bs_current_liabilities")
    out["liabilities_to_assets"] = (col("bs_current_liabilities") + col("bs_noncurrent_liabilities")) / col(
        "bs_total_assets")
    out["revenue_per_employee_thousand_kzt"] = rev / col("avg_headcount")
    detailed = out[["share_state_order_in_revenue", "share_paid_tuition_in_revenue", "share_research_in_revenue",
                    "share_revenue_rent", "share_revenue_other"]].max(axis=1)
    coarse = out[["share_revenue_services", "share_revenue_rent", "share_revenue_other"]].max(axis=1)
    has_detail = col("services_state_order").notna()
    out["largest_revenue_source_share"] = detailed.where(has_detail, coarse)
    out["equity"] = col("bs_equity")
    return out


LABELS = {
    "share_revenue_services": "Доля услуг в доходах",
    "share_revenue_rent": "Доля аренды в доходах",
    "share_revenue_other": "Доля прочих доходов",
    "share_state_order_in_revenue": "Госзаказ / все доходы",
    "share_paid_tuition_in_revenue": "Платное обучение / все доходы",
    "share_research_in_revenue": "Научный проект / все доходы",
    "share_payroll_with_social_in_expenses": "Оплата труда с соцотчислениями / расходы",
    "share_depreciation_in_expenses": "Амортизация / расходы",
    "share_interest_in_expenses": "Проценты / расходы",
    "current_ratio": "Коэффициент текущей ликвидности",
    "liabilities_to_assets": "Обязательства / активы",
    "revenue_per_employee_thousand_kzt": "Доходы на одного работника, тыс. тенге",
    "largest_revenue_source_share": "Доля крупнейшего источника дохода (2019: без разбивки услуг)",
    "equity": "Капитал, тыс. тенге",
}

CAVEATS = [
    "Цифры прочитаны с отсканированного PDF финансовой отчётности за 2020 год (тыс. тенге) и не сверены "
    "с оригиналом: verified=false, номера страниц нужно уточнить.",
    "Это два года, 2019 и 2020, и 2020 — второй год работы вуза. Тренды по ним оценивать нельзя.",
    "Расходы 2020 года включают возмещение коммунальных услуг и налога на имущество сразу за 2019 и 2020 годы "
    "(397 400 тыс. тенге), поэтому структура расходов 2020 года нетипична.",
    "Доля «госзаказа» — это доход от государственного образовательного заказа, а не все бюджетные деньги.",
]


def main():
    df = load()
    checks = sum_checks(df)
    print(checks.to_string(index=False))
    bad = checks[~checks["ok"]]
    print("\nРасхождения больше 1 тыс. тенге:" if len(bad) else "\nРасхождений больше 1 тыс. тенге нет.")
    if len(bad):
        print(bad.to_string(index=False))
    print(structure(df).T.round(4).to_string())


if __name__ == "__main__":
    main()
