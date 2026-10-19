"""Fact builders. They READ saved results; no model is trained or re-evaluated here.

If a source file is missing, the builder emits facts with status "нет данных" (value None)
so the registry still shows what is expected and where it would come from.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

import pandas as pd

from src.advisor.facts.schema import Fact
from src.config import BASE_DIR

ROOT = BASE_DIR
FACULTIES = ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG"]
MIN_GROUP = 30

ACADEMIC_CAVEAT = ("Демо-данные OULAD (Open University, Великобритания), факультеты условные. Риск оценён вне "
                   "обучающей выборки (GroupKFold по студенту) по данным недель ≤ k, только ещё учащиеся.")
AUDIT_CAVEAT = "Набор OULAD (Open University, Великобритания), не данные AITU. Пересчёт аудита Academic."
RESEARCH_PANEL_CAVEAT = ("Панель 13 вузов Казахстана (OpenAlex), rolling origin; выигрыш MAE роста над naive. "
                         "Критерий зафиксирован до моделей (STAGE2_REPORT.md).")
FINANCE_CAVEAT = "Данные США (IPEDS), контекст другой. Критерий зафиксирован до моделей (src/finance/criterion.py)."
AITU_CAVEAT = ("Снимок 2020 года, цифры с отсканированного PDF (verified=false). Два года отчётности — тренды "
               "оценивать нельзя.")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def _read(path: Path) -> pd.DataFrame | None:
    return pd.read_csv(path) if path.exists() else None


def _num(x):
    if x is None:
        return None
    if isinstance(x, bool):
        return x
    try:
        v = float(x)
    except (TypeError, ValueError):
        return x
    return None if math.isnan(v) else v


def _fact(**kw) -> Fact:
    if kw.get("value") is None and kw.get("status") != "нет данных":
        kw["status"] = "нет данных"
        kw["caveat"] = kw.get("caveat", "") + " Файл результата не найден."
    return Fact(**{k: (_num(v) if k == "value" else v) for k, v in kw.items()})


# ── Academic ───────────────────────────────────────────────────────────────────────────

def academic() -> list[Fact]:
    facts = []
    src = ROOT / "results/academic_audit/risk_model_eval.csv"
    d = _read(src)
    metrics = {"auc": ("AUC модели риска", "auc"), "precision_top10": ("Precision в топ-10% риска", "share"),
               "recall_top10": ("Охват ушедших в топ-10% риска", "share"), "brier": ("Brier score", "brier"),
               "n": ("Ещё учащихся (оценка)", "count"), "base_rate": ("Доля ушедших позже среди ещё учащихся", "share")}
    for k in (5, 10, 20):
        variant = f"after: k={k}, still enrolled, out-of-fold"
        for mod in ["ALL"] + FACULTIES:
            row = None if d is None else d[(d["variant"] == variant) & (d["module"] == mod)]
            row = None if row is None or row.empty else row.iloc[0]
            name = "все факультеты" if mod == "ALL" else f"факультет {mod}"
            for m, (label, unit) in metrics.items():
                facts.append(_fact(
                    id=f"academic.risk.k{k}.{mod.lower()}.{m}", module="academic", metric=f"{label}, {name}",
                    value=None if row is None else row[m], unit=unit, period=f"неделя k = {k}", status="демо",
                    source=rel(src), caveat=ACADEMIC_CAVEAT, group=f"k={k}|{mod}",
                    tags=["risk_model"]))
            # risk groups: aggregates only, groups of at least MIN_GROUP students
            if row is not None:
                size = math.ceil(0.10 * row["n"])
                ok = size >= MIN_GROUP
                facts.append(_fact(
                    id=f"academic.riskgroup.k{k}.{mod.lower()}.high_size", module="academic",
                    metric=f"Размер группы высокого риска (топ-10%), {name}", value=size if ok else None,
                    unit="count", period=f"неделя k = {k}", status="демо" if ok else "нет данных", source=rel(src),
                    caveat=ACADEMIC_CAVEAT + (" " if ok else f" Группа меньше {MIN_GROUP} — не показывается."),
                    group=f"k={k}|{mod}", tags=["risk_groups"]))
                facts.append(_fact(
                    id=f"academic.riskgroup.k{k}.{mod.lower()}.high_withdrawn_share", module="academic",
                    metric=f"Доля реально ушедших в группе высокого риска, {name}",
                    value=row["precision_top10"] if ok else None, unit="share", period=f"неделя k = {k}",
                    status="демо" if ok else "нет данных", source=rel(src),
                    caveat=ACADEMIC_CAVEAT + " Это проверка модели на прошлых данных, не прогноз по людям.",
                    group=f"k={k}|{mod}", tags=["risk_groups"]))
    old = None if d is None else d[(d["variant"] == "before: in-sample, all students, full course")
                                   & (d["module"] == "ALL")]
    facts.append(_fact(
        id="academic.risk.before.all.auc", module="academic",
        metric="AUC прежней модели риска (оценка на обучающих данных, признаки за весь курс)",
        value=None if old is None or old.empty else old.iloc[0]["auc"], unit="auc", period="весь курс",
        status="демо", source=rel(src),
        caveat="Завышенная оценка: модель видела весь курс и проверялась на тех же студентах. Заменена в 7af6091."))

    st = _read(ROOT / "results/academic_audit/static_auc.csv")
    src2 = rel(ROOT / "results/academic_audit/static_auc.csv")
    for model in ("RF", "LR"):
        for k in (5, 10, 20):
            for pop, pname in (("all", "все тестовые регистрации"), ("still_enrolled", "ещё учащиеся")):
                row = None if st is None else st[(st["model"] == model) & (st["k"].astype(str) == str(k))
                                                  & (st["population"] == pop)]
                facts.append(_fact(
                    id=f"academic.audit.{model.lower()}.k{k}.{pop}.auc", module="academic",
                    metric=f"AUC {model} на признаках недель ≤ k ({pname})",
                    value=None if row is None or row.empty else row.iloc[0]["auc"], unit="auc",
                    period=f"неделя k = {k}", status="проверено", source=src2, caveat=AUDIT_CAVEAT,
                    group=f"k={k}|{pop}", tags=["audit"]))
    return facts


# ── Research ───────────────────────────────────────────────────────────────────────────

COUNT_TARGETS = {"works_count": "число публикаций", "unique_authors": "число уникальных авторов",
                 "citations_received_in_year": "цитирования за год"}
SHARE_TARGETS = {"citations_per_author": "цитирования на автора", "fwci_median": "медианный FWCI",
                 "intl_collab_share": "доля международных соавторств", "top10_share": "доля работ в топ-10%"}


def research() -> list[Fact]:
    facts = []
    src = ROOT / "results/research/stage2/summary.csv"
    d = _read(src)
    for target, label in {**COUNT_TARGETS, **SHARE_TARGETS}.items():
        kind = "счётчик" if target in COUNT_TARGETS else "доля или отношение"
        best = None
        if d is not None:
            m = d[(d["scenario"] == "main") & (d["subset"] == "main") & (d["scheme"] == "rolling")
                  & (d["target"] == target) & (d["model"] != "naive")]
            best = None if m.empty else m.loc[m["gain_vs_naive"].idxmax()]
        base = dict(module="research", period="rolling origin, панель 2010–2025", source=rel(src),
                    caveat=RESEARCH_PANEL_CAVEAT, group=target, tags=["research_panel", kind])
        facts.append(_fact(id=f"research.panel.{target}.best_gain", metric=f"Выигрыш лучшей модели над naive: "
                           f"{label} ({kind})", value=None if best is None else best["gain_vs_naive"], unit="gain",
                           status="проверено", **base))
        facts.append(_fact(id=f"research.panel.{target}.best_model", metric=f"Лучшая модель: {label}",
                           value=None if best is None else str(best["model"]), unit="text", status="проверено",
                           **base))
        facts.append(_fact(id=f"research.panel.{target}.passed", metric=f"Критерий пройден: {label}",
                           value=None if best is None else bool(best["success"]), unit="bool", status="проверено",
                           **base))
    raw = ROOT / "data/research/raw/yearly_work_counts_I4405257690.json"
    counts = {}
    if raw.exists():
        counts = {int(g["key"]): int(g["count"]) for g in json.loads(raw.read_text())["group_by"]}
    for year in range(2019, 2027):
        partial = year == 2026
        facts.append(_fact(
            id=f"research.aitu.works.y{year}", module="research", metric=f"Публикации AITU в OpenAlex, {year}",
            value=counts.get(year), unit="count", period=str(year),
            status="исследовательское" if partial else "проверено", source=rel(raw),
            caveat=("Неполный год: данные на дату выгрузки." if partial else
                    "Копия ответа OpenAlex в репозитории; учитываются работы с аффилиацией AITU."),
            group="aitu", tags=["aitu_publications"]))
    bt_src = ROOT / "results/research/metrics/research_backtest.csv"
    bt = _read(bt_src)
    cav = ("Иллюстрация: proof-of-concept на 5 годовых точках (2020–2024), проверка на одном отложенном "
           "годе, не кросс-валидация. Потолок логистической модели — экспертная оценка.")
    actual = None if bt is None else bt.iloc[0]["actual"]
    facts.append(_fact(id="research.aitu.backtest2025.actual", module="research",
                       metric="Публикации AITU 2025 (факт для бэктеста)", value=actual, unit="count", period="2025",
                       status="исследовательское", source=rel(bt_src), caveat=cav, tags=["illustration"]))
    for growth, name in (("linear", "линейный рост"), ("logistic", "логистический рост")):
        row = None if bt is None else bt[bt["growth"] == growth]
        row = None if row is None or row.empty else row.iloc[0]
        facts.append(_fact(id=f"research.aitu.backtest2025.{growth}_pred", module="research",
                           metric=f"Прогноз публикаций AITU на 2025 по данным до 2024 ({name}), иллюстрация",
                           value=None if row is None else row["predicted"], unit="count", period="2025",
                           status="исследовательское", source=rel(bt_src), caveat=cav, tags=["illustration"]))
        facts.append(_fact(id=f"research.aitu.backtest2025.{growth}_error", module="research",
                           metric=f"Ошибка прогноза на 2025 ({name}), иллюстрация",
                           value=None if row is None else row["pct_error"] / 100, unit="share", period="2025",
                           status="исследовательское", source=rel(bt_src), caveat=cav, tags=["illustration"]))
    return facts + research_stage3()


STAGE3_TARGETS = {
    "works_count": "публикации", "unique_authors": "уникальные авторы",
    "citations_received_in_year": "цитирования за год", "intl_collab_share": "доля международных соавторств",
    "top10_share": "доля работ в топ-10%", "n_partner_countries": "число стран-партнёров",
    "n_intl_works": "международные работы", "n_partner_institutions": "организации-партнёры",
}
STAGE3_CAVEAT = ("Панель 50 вузов (Казахстан 35, Турция 7, Россия 4 и др.), OpenAlex на 2026-10-19, rolling origin и "
                 "leave-one-university-out 2019–2025. Критерии C1 и C2 и основная модель зафиксированы до запуска "
                 "(src/research/criterion_stage3.py, STAGE3_REPORT.md).")
AITU_BENCH_CAVEAT = ("Описательный бенчмарк, не причинность: положение AITU среди 50 вузов панели в 2025. "
                     "Не говорит, почему так и что изменится от каких-либо действий.")


def research_stage3() -> list[Fact]:
    facts = []
    d = ROOT / "results/research/stage3"
    v_src, c_src, cov_src = d / "verdicts.csv", d / "criteria_all_models.csv", d / "conformal_coverage.csv"
    v, cr, cov = _read(v_src), _read(c_src), _read(cov_src)
    period, tags = "прогноз на год, 2019–2025", ["research_stage3"]
    for target, label in STAGE3_TARGETS.items():
        row = None if v is None else v[(v["panel"] == "extended") & (v["target"] == target)]
        row = None if row is None or row.empty else row.iloc[0]
        g = dict(module="research", period=period, tags=tags, group=target, source=rel(v_src),
                 caveat=STAGE3_CAVEAT, status="проверено")
        for scheme, sname in (("rolling", "rolling origin"), ("louo", "leave-one-university-out")):
            facts.append(_fact(id=f"research.stage3.{target}.c1_gain_{scheme}",
                               metric=f"Выигрыш основной модели над naive, {label}, {sname}", unit="gain",
                               value=None if row is None else row[f"C1_gain_{scheme}"], **g))
        facts.append(_fact(id=f"research.stage3.{target}.c1_passed", metric=f"Критерий C1 (лучше naive) пройден: {label}",
                           unit="bool", value=None if row is None else bool(row["C1"]), **g))
        facts.append(_fact(id=f"research.stage3.{target}.c2_passed",
                           metric=f"Критерий C2 (лучше среднего роста панели и возрастной группы) пройден: {label}",
                           unit="bool", value=None if row is None else bool(row["C2"]), **g))
        o13 = None if v is None else v[(v["panel"] == "orig13") & (v["target"] == target)]
        facts.append(_fact(id=f"research.stage3.{target}.c1_passed_orig13", module="research", period=period,
                           metric=f"C1 на исходных 13 вузах (сравнение): {label}", unit="bool",
                           value=None if o13 is None or o13.empty else bool(o13.iloc[0]["C1"]),
                           status="исследовательское", source=rel(v_src), group=target, tags=tags,
                           caveat="Сравнение на 13 вузах этапа 2; мощность мала, результат зависит от даты выгрузки."))
        cv = None if cov is None else cov[cov["target"] == target]
        facts.append(_fact(id=f"research.stage3.{target}.conformal_coverage", module="research", period=period,
                           metric=f"Покрытие 80% конформного интервала: {label}", unit="share",
                           value=None if cv is None or cv.empty else cv.iloc[0]["all"], status="проверено",
                           source=rel(cov_src), group=target, tags=tags,
                           caveat="Номинал 80%; выше номинала — интервалы шире нужного."))
    ex = None if cr is None else cr[(cr["panel"] == "extended") & (cr["target"] == "n_partner_countries")
                                    & (cr["model"] == "ridge") & (cr["baseline"] != "naive")]
    facts.append(_fact(id="research.stage3.exploratory.ridge_partner_countries_c2", module="research",
                       metric="Ridge (не основная модель) лучше обоих средних ростов: число стран-партнёров",
                       value=None if ex is None or ex.empty else bool(ex["passes"].all()), unit="bool",
                       period=period, status="исследовательское", source=rel(c_src), tags=tags,
                       caveat="Неосновная модель: результат исследовательский, нужна отдельная предрегистрация."))
    f_src = d / "aitu_forecast.csv"
    fc = _read(f_src)
    cav = ("Модель обучена на 50 вузах панели; C2 не пройден — прогноз не доказанно лучше среднего роста. "
           "Интервал — конформный 80%. Данные OpenAlex на 2026-10-19.")
    for target, label in STAGE3_TARGETS.items():
        row = None if fc is None else fc[fc["target"] == target]
        row = None if row is None or row.empty else row.iloc[0]
        if row is not None and row["status"] != "прогноз":
            facts.append(_fact(id=f"research.aitu.stage3.{target}.forecast_2026", module="research",
                               metric=f"Прогноз AITU на 2026: {label}", value=str(row["status"]), unit="text",
                               period="2026", status="исследовательское", source=rel(f_src), group=target,
                               caveat="Критерий C1 для этой цели не пройден.", tags=["aitu_stage3"]))
            continue
        unit = "share" if target.endswith("_share") else "count"
        for part, pname in (("forecast", "прогноз"), ("lower80", "нижняя граница 80%"),
                            ("upper80", "верхняя граница 80%")):
            facts.append(_fact(id=f"research.aitu.stage3.{target}.{part}_2026", module="research",
                               metric=f"AITU 2026, {label}: {pname}", value=None if row is None else row[part],
                               unit=unit, period="2026", status="исследовательское", source=rel(f_src),
                               group=target, caveat=cav, tags=["aitu_stage3"]))
    p_src = d / "aitu_percentiles.csv"
    pc = _read(p_src)
    for metric, label in (("works_count", "публикации"), ("citations_per_author", "цитирования на автора"),
                          ("intl_collab_share", "доля международных соавторств"),
                          ("n_partner_countries", "число стран-партнёров")):
        row = None if pc is None else pc[pc["metric"] == metric]
        row = None if row is None or row.empty else row.iloc[0]
        facts.append(_fact(id=f"research.aitu.stage3.percentile.{metric}", module="research",
                           metric=f"Процентиль AITU среди 50 вузов панели: {label}",
                           value=None if row is None else row["percentile"] / 100, unit="share", period="2025",
                           status="исследовательское", source=rel(p_src), group=metric, caveat=AITU_BENCH_CAVEAT,
                           tags=["aitu_stage3", "benchmark"]))
    return facts


# ── Finance ────────────────────────────────────────────────────────────────────────────

TARGET_RU = {"retention_rate": "retention первокурсников", "grad_rate_150": "выпускаемость за 150% срока",
             "fall_enrollment": "осенний приём", "core_total_per_fte_real": "core-расходы на FTE"}
SCOPE_RU = {"all_years": "все годы", "excluding_flagged": "без помеченных лет"}
MODEL_RU = {"lgbm_S3": "LightGBM S3 (основная)", "ridge_S1": "Ridge S1", "ridge_S3": "Ridge S3",
            "lgbm_S1": "LightGBM S1", "constant": "константа"}


def finance() -> list[Fact]:
    facts = []
    d2 = ROOT / "results/finance/stage2"
    crit = _read(d2 / "criterion_rolling.csv")
    for target, tname in TARGET_RU.items():
        passed_all = None
        for scope, sname in SCOPE_RU.items():
            for model, mname in MODEL_RU.items():
                row = None if crit is None else crit[(crit["target"] == target) & (crit["model"] == model)
                                                     & (crit["scope"] == scope)]
                row = None if row is None or row.empty else row.iloc[0]
                prefix = "criterion" if model == "lgbm_S3" else f"ablation.{model.lower()}"
                facts.append(_fact(
                    id=f"finance.{prefix}.{target}.{scope}.gain", module="finance",
                    metric=f"Выигрыш над naive, {tname}, {mname}, {sname}",
                    value=None if row is None else row["gain_vs_naive"], unit="gain", period="origin 2014–2022",
                    status="проверено", source=rel(d2 / "criterion_rolling.csv"),
                    caveat=FINANCE_CAVEAT + (" Порог 10% и ДИ ниже нуля в обеих оценках." if model == "lgbm_S3"
                                             else " Вторичная модель (абляция); проход критерия ею — поисковый."),
                    group=target, tags=["finance_criterion"]))
                if model == "lgbm_S3" and row is not None:
                    passed_all = bool(row["meets_success_rule"]) if passed_all is None else (
                        passed_all and bool(row["meets_success_rule"]))
        facts.append(_fact(
            id=f"finance.criterion.{target}.passed", module="finance",
            metric=f"Основная модель прошла критерий: {tname}", value=passed_all, unit="bool",
            period="origin 2014–2022", status="проверено", source=rel(d2 / "criterion_rolling.csv"),
            caveat=FINANCE_CAVEAT, group=target, attention=passed_all is False, tags=["finance_criterion"]))
    uns = _read(d2 / "criterion_unseen_summary.csv")
    for target, tname in TARGET_RU.items():
        for scope, sname in SCOPE_RU.items():
            row = None if uns is None else uns[(uns["target"] == target) & (uns["model"] == "lgbm_S3")
                                               & (uns["scope"] == scope)]
            facts.append(_fact(
                id=f"finance.unseen.{target}.{scope}.splits_passing", module="finance",
                metric=f"Невиданные вузы: разбиений из 5, прошедших критерий, {tname}, {sname}",
                value=None if row is None or row.empty else row.iloc[0]["splits_passing"], unit="count",
                period="origin 2016, 2019, 2022", status="проверено",
                source=rel(d2 / "criterion_unseen_summary.csv"), caveat=FINANCE_CAVEAT, group=target))
    cov = _read(d2 / "interval_coverage.csv")
    for target, tname in TARGET_RU.items():
        row = None if cov is None else cov[(cov["target"] == target) & (cov["breakdown"] == "all")]
        facts.append(_fact(
            id=f"finance.interval.{target}.coverage", module="finance",
            metric=f"Эмпирическое покрытие 80%-интервала, {tname}",
            value=None if row is None or row.empty else row.iloc[0]["coverage"], unit="share",
            period="целевые годы 2015–2023", status="проверено", source=rel(d2 / "interval_coverage.csv"),
            caveat=FINANCE_CAVEAT, group=target))
    hyp = _read(d2 / "hypotheses.csv")
    names = {"H1": "доля студенческих сервисов → retention", "H2": "доля преподавания → выпускаемость",
             "H3": "доля академической поддержки → retention", "H4": "доля институциональной поддержки → выпускаемость"}
    hcav = ("Связь, не эффект: FE вуза и года на первых разностях, данные США. Гипотезы зафиксированы до расчёта.")
    for h, label in names.items():
        main = None if hyp is None else hyp[(hyp["hypothesis"] == h) & (hyp["spec"] == "main")]
        main = None if main is None or main.empty else main.iloc[0]
        pl = None if hyp is None else hyp[(hyp["hypothesis"] == h) & (hyp["spec"] == "placebo_lead")]
        base = dict(module="finance", period="2011–2023 (выпускаемость 2016–2023)",
                    source=rel(d2 / "hypotheses.csv"), caveat=hcav, group=h, tags=["hypotheses"])
        facts.append(_fact(id=f"finance.{h.lower()}.beta", metric=f"{h}: связь ({label}), п.п. результата на "
                           "+1 п.п. доли", value=None if main is None else main["beta"], unit="pp",
                           status="проверено", **base))
        facts.append(_fact(id=f"finance.{h.lower()}.ci_lo", metric=f"{h}: нижняя граница 95% ДИ",
                           value=None if main is None else main["ci_lo"], unit="pp", status="проверено", **base))
        facts.append(_fact(id=f"finance.{h.lower()}.ci_hi", metric=f"{h}: верхняя граница 95% ДИ",
                           value=None if main is None else main["ci_hi"], unit="pp", status="проверено", **base))
        facts.append(_fact(id=f"finance.{h.lower()}.p_holm", metric=f"{h}: p с поправкой Холма",
                           value=None if main is None else main["p_holm"], unit="p_value", status="проверено",
                           **base))
        facts.append(_fact(id=f"finance.{h.lower()}.verdict", metric=f"{h}: вывод",
                           value=None if main is None else {"no association detected": "связь не обнаружена",
                                                            "association supported": "связь подтверждена",
                                                            "association in the opposite direction":
                                                                "связь в обратную сторону"}.get(main["verdict"],
                                                                                                main["verdict"]),
                           unit="text", status="проверено", **base))
        facts.append(_fact(id=f"finance.{h.lower()}.placebo_p", metric=f"{h}: p плацебо (опережающая доля)",
                           value=None if pl is None or pl.empty else pl.iloc[0]["p"], unit="p_value",
                           status="проверено", **base))
    ma3 = _read(d2 / "exploratory_ma3.csv")
    for target, tname in TARGET_RU.items():
        for comp, cid, cname in (("MA3 vs naive", "ma3_vs_naive", "скользящее среднее за 3 года против naive"),
                                 ("lgbm_S3 vs MA3", "lgbm_vs_ma3", "LightGBM S3 против скользящего среднего")):
            row = None if ma3 is None else ma3[(ma3["target"] == target) & (ma3["comparison"] == comp)
                                               & (ma3["scope"] == "all_years")]
            facts.append(_fact(
                id=f"finance.ma3.{target}.{cid}", module="finance", metric=f"{cname}, {tname}, все годы",
                value=None if row is None or row.empty else row.iloc[0]["gain_vs_reference"], unit="gain",
                period="origin 2014–2022", status="исследовательское", source=rel(d2 / "exploratory_ma3.csv"),
                caveat="Исследовательское (после основного прогона), в критерий не входит. " + FINANCE_CAVEAT,
                group=target, tags=["exploratory"]))
    return facts


# ── AITU profile ───────────────────────────────────────────────────────────────────────

def aitu() -> list[Fact]:
    from src.finance import aitu_profile

    facts = []
    src = ROOT / "data/aitu/financials_2019_2020.csv"
    df = aitu_profile.load(src)
    labels = aitu_profile.LABELS
    keep = ["share_state_order_in_revenue", "share_paid_tuition_in_revenue", "share_research_in_revenue",
            "share_payroll_with_social_in_expenses", "share_depreciation_in_expenses", "share_interest_in_expenses",
            "share_exp_taxes_in_expenses", "share_exp_other_in_expenses", "current_ratio", "liabilities_to_assets",
            "revenue_per_employee_thousand_kzt", "largest_revenue_source_share", "equity"]
    units = {"current_ratio": "ratio", "liabilities_to_assets": "ratio", "equity": "kzt_thousand",
             "revenue_per_employee_thousand_kzt": "kzt_thousand"}
    for variant, vname in aitu_profile.VARIANTS.items():
        s = aitu_profile.structure(df, exclude_one_off=variant == "excl_one_off")
        for year in s.index:
            for m in keep:
                expense = m.endswith("_in_expenses")
                if variant == "excl_one_off" and not expense:
                    continue
                v = s.at[year, m]
                if pd.isna(v):
                    continue
                suffix = (", без разовой статьи 2019–2020" if variant == "excl_one_off" else ", все расходы") \
                    if expense else ""
                facts.append(_fact(
                    id=f"aitu.y{year}.{m}" + (".excl_one_off" if variant == "excl_one_off" else ""), module="aitu",
                    metric=f"{labels.get(m, m)}{suffix}", value=v, unit=units.get(m, "share"), period=str(year),
                    status="исследовательское", source=rel(src),
                    caveat=AITU_CAVEAT + (f" Вариант расходов: {vname}." if expense else ""), group=str(year),
                    attention=(m == "equity" and v < 0) or (m == "current_ratio" and v < 1),
                    tags=["aitu_profile", variant]))
    rules_src = ROOT / "results/finance/stage2/aitu_rules.csv"
    r = _read(rules_src)
    if r is not None:
        r = r[r["year"] == 2020]
        for _, row in r.iterrows():
            vid = "" if row["variant"] == "all" else ".excl_one_off"
            cav = (f"Источник порога: {row['source']} ({row['status']}). " + AITU_CAVEAT
                   + (f" {row['caveat']}" if isinstance(row["caveat"], str) and row["caveat"] else ""))
            trig = row["triggered"]
            trig = None if pd.isna(trig) else str(trig) == "True"
            facts.append(_fact(
                id=f"aitu.rule.{row['rule']}{vid}.triggered", module="aitu",
                metric=f"Флаг правила: {row['label']} ({row['variant_label']})",
                value=trig, unit="bool", period="2020", status="исследовательское" if trig is not None else "нет данных",
                source=rel(rules_src), caveat=cav, attention=trig is True, tags=["aitu_rules"]))
            m = re.match(r"P10–P90 = ([\d.]+)–([\d.]+) \(n=(\d+), медиана ([\d.]+)\)", str(row["threshold"]))
            if m and row["variant"] == "all":
                p10, p90, n, p50 = float(m[1]), float(m[2]), int(m[3]), float(m[4])
                base = dict(module="aitu", period="США 2019–2021", source=rel(rules_src), status="проверено",
                            caveat="Государственные вузы США Carnegie Master's (IPEDS), ориентир США, контекст другой.",
                            group=row["rule"], tags=["us_peers"])
                facts += [_fact(id=f"aitu.us_peers.{row['rule']}.p10", metric=f"Аналоги США P10: {row['label']}",
                                value=p10, unit="share", **base),
                          _fact(id=f"aitu.us_peers.{row['rule']}.p50", metric=f"Аналоги США медиана: {row['label']}",
                                value=p50, unit="share", **base),
                          _fact(id=f"aitu.us_peers.{row['rule']}.p90", metric=f"Аналоги США P90: {row['label']}",
                                value=p90, unit="share", **base),
                          _fact(id=f"aitu.us_peers.{row['rule']}.n", metric=f"Аналоги США, число вузов: {row['label']}",
                                value=n, unit="count", **base)]
            if isinstance(row.get("position"), str) and row["position"]:
                facts.append(_fact(
                    id=f"aitu.position.{row['rule']}{vid}", module="aitu",
                    metric=f"Положение AITU среди аналогов США: {row['label']} ({row['variant_label']})",
                    value=row["position"], unit="text", period="2020", status="исследовательское",
                    source=rel(rules_src), caveat=cav, tags=["us_peers"]))
    return facts


# ── Modules and capability matrix ──────────────────────────────────────────────────────

CAPABILITIES = [
    # direction, what it can do, what it cannot, status
    ("academic", "Академическое направление",
     "Риск отчисления на неделе k = 5/10/20 вне обучающей выборки; качество модели (AUC, precision и охват в топ-10%, "
     "калибровка); главные факторы риска по SHAP.",
     "Работает на демо-данных OULAD с условными факультетами; на данных AITU не проверено. Не выносит решений "
     "по конкретным студентам.", "демо"),
    ("research", "Наука и инновации",
     "Ряд публикаций AITU из OpenAlex; модели роста против naive на панели 13 вузов Казахстана: для счётчиков "
     "(публикации, авторы, цитирования) критерий пройден.",
     "Для долей (международные соавторства, топ-10%, FWCI) модели не лучше naive. Прогноз AITU — иллюстрация "
     "на 5 точках.", "проверено"),
    ("finance", "Экономика и финансы",
     "Прогноз 4 показателей вузов США с проверкой против критерия; бенчмарк структуры расходов; профиль AITU "
     "2019–2020 с правилами.",
     "Основная модель не прошла критерий ни по одной цели; связь структуры бюджета и результатов не обнаружена "
     "(и это не эффект). Профиль AITU — два года с отсканированного PDF.", "проверено"),
    ("international", "Интернационализация",
     "Только доля международных соавторств в публикациях (панель OpenAlex), без прогноза лучше naive.",
     "Мобильность студентов и преподавателей, иностранные студенты, партнёрства, программы двойного диплома — "
     "данных нет.", "нет данных"),
    ("upbringing", "Воспитательная работа",
     "Ничего: модуль не реализован.",
     "Нет данных о внеучебной деятельности, кураторстве, волонтёрстве, общежитиях, удовлетворённости студентов.",
     "нет данных"),
    ("digital", "Цифровизация",
     "Состояние данных и моделей системы (страница «Что проверено»); журнал запросов к советнику без "
     "персональных данных.",
     "Нет данных об ИТ-инфраструктуре вуза, использовании LMS AITU, цифровых сервисах.", "нет данных"),
]
NEEDED_DATA = {
    "international": ["число иностранных студентов по годам и странам", "исходящая и входящая академическая "
                      "мобильность студентов и ППС", "договоры о партнёрстве и их активность",
                      "программы двойного диплома и набор на них", "позиции в международных рейтингах по годам"],
    "upbringing": ["участие студентов во внеучебной деятельности (клубы, спорт, волонтёрство)",
                   "кураторские встречи и обращения студентов", "проживание в общежитии",
                   "опросы удовлетворённости и благополучия студентов", "дисциплинарные случаи (агрегаты)"],
    "digital": ["активность в LMS AITU по неделям (агрегаты)", "доступность и использование цифровых сервисов",
                "инциденты и обращения в ИТ-поддержку"],
}


def capabilities() -> list[Fact]:
    facts = []
    src = "docs/ADVISOR_UI_PLAN.md"
    for key, name, can, cannot, status in CAPABILITIES:
        cav = "Матрица возможностей по состоянию кода и сохранённых результатов."
        facts.append(Fact(id=f"system.capability.{key}.can", module="system", metric=f"{name}: что система умеет",
                          value=can, unit="text", period="2026-10", status=status if status != "нет данных" else
                          "нет данных", source=src, caveat=cav, group=key, tags=["capabilities"]))
        facts.append(Fact(id=f"system.capability.{key}.cannot", module="system",
                          metric=f"{name}: чего система не умеет", value=cannot, unit="text", period="2026-10",
                          status="проверено", source=src, caveat=cav, group=key, tags=["capabilities"]))
        facts.append(Fact(id=f"system.module.{key}.status", module="system", metric=f"Статус модуля: {name}",
                          value=status, unit="text", period="2026-10", status="проверено", source=src,
                          caveat=cav, group=key, tags=["modules"]))
    for key, items in NEEDED_DATA.items():
        facts.append(Fact(id=f"system.needed_data.{key}", module="system",
                          metric=f"Что нужно собрать: {dict((c[0], c[1]) for c in CAPABILITIES)[key]}",
                          value="; ".join(items), unit="text", period="2026-10", status="нет данных", source=src,
                          caveat="Модуль не реализован, данных нет.", group=key, tags=["needed_data"]))
    return facts
