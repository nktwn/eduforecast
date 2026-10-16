import sys
from pathlib import Path

for _p in (Path(__file__).resolve().parents[1], Path(__file__).resolve().parents[2]):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from components import ui  # noqa: E402
from src.advisor.facts.fmt import format_value  # noqa: E402
from src.advisor.facts.registry import registry  # noqa: E402
from src.advisor.facts.schema import STATUSES  # noqa: E402

REG = registry()
MODULES = [("academic", "Академический"), ("research", "Научный"), ("finance", "Финансы"),
           ("international", "Международный"), ("upbringing", "Воспитательный"), ("digital", "Цифровизация")]
REPORTS = [("ACADEMIC_AUDIT.md", "Academic: утечки, оценка на неделе k, LSTM / TFT"),
           ("audit/academic/README.md", "Academic: воспроизводимые скрипты аудита"),
           ("results/academic_audit/paper_vs_recomputed.md", "Academic: числа статьи против пересчёта"),
           ("DATA_AUDIT.md", "Research: панель OpenAlex"), ("STAGE2_REPORT.md", "Research: модели против naive"),
           ("FINANCE_DATA_AUDIT.md", "Finance: данные IPEDS и baseline"),
           ("FINANCE_STAGE2_REPORT.md", "Finance: критерий, связь бюджета, профиль AITU"),
           ("docs/ADVISOR_AND_UI_REPORT.md", "Советник и интерфейс")]
KEY_METRICS = ["academic.risk.k5.all.auc", "academic.risk.k5.all.precision_top10", "academic.audit.rf.k5.all.auc",
               "research.panel.works_count.best_gain", "research.panel.intl_collab_share.best_gain",
               "finance.criterion.retention_rate.all_years.gain",
               "finance.criterion.retention_rate.excluding_flagged.gain", "finance.criterion.retention_rate.passed",
               "finance.criterion.core_total_per_fte_real.passed", "finance.h1.verdict", "finance.h2.verdict",
               "aitu.y2020.current_ratio", "research.aitu.backtest2025.logistic_error"]

ui.page_header("Что проверено", "Методика: статусы модулей, ключевые метрики, ограничения, отчёты аудита.")
st.markdown("**Статусы.** " + " · ".join(f"{ui.badge_html(s)} {ui.esc(ui.STATUS_HELP[s])}" for s in STATUSES),
            unsafe_allow_html=True)

st.markdown('<div class="section-title">Модули и матрица возможностей</div>', unsafe_allow_html=True)
rows = [{"Направление": name, "Статус": REG.get(f"system.module.{k}.status")["value"],
         "Что умеет": REG.get(f"system.capability.{k}.can")["value"],
         "Чего не умеет": REG.get(f"system.capability.{k}.cannot")["value"]} for k, name in MODULES]
st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

st.markdown('<div class="section-title">Ключевые метрики</div>', unsafe_allow_html=True)
st.dataframe(pd.DataFrame([{"Показатель": REG.get(i)["metric"], "Значение": REG.display(i),
                            "Статус": REG.get(i)["status"], "Период": REG.get(i)["period"],
                            "Источник": REG.get(i)["source"]} for i in KEY_METRICS if REG.get(i)]),
             hide_index=True, width="stretch")

st.markdown('<div class="section-title">Отчёты аудита</div>', unsafe_allow_html=True)
root = Path(__file__).resolve().parents[2]
for path, desc in REPORTS:
    mark = "" if (root / path).exists() else " (нет в этой копии)"
    st.markdown(f"- `{path}` — {desc}{mark}")

st.markdown('<div class="section-title">Реестр фактов</div>', unsafe_allow_html=True)
c1, c2, c3 = st.columns([1, 1, 2])
mod = c1.selectbox("Модуль", ["все"] + sorted({f["module"] for f in REG.facts.values()}))
status = c2.selectbox("Статус", ["все"] + list(STATUSES))
query = c3.text_input("Поиск по названию", "")
facts = [f for f in REG.facts.values() if (mod == "все" or f["module"] == mod)
         and (status == "все" or f["status"] == status) and query.lower() in f["metric"].lower()]
st.caption(f"Фактов: {len(facts)} из {len(REG.facts)}; реестр собран "
           f"{ui.theme.ru_date(REG.built_at, with_time=True)}.")
st.dataframe(pd.DataFrame([{"id": f["id"], "Показатель": f["metric"], "Значение": format_value(f["value"], f["unit"]),
                            "Статус": f["status"], "Оговорка": f["caveat"], "Источник": f["source"]}
                           for f in facts]), hide_index=True, width="stretch", height=420)
