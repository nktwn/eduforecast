import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import streamlit as st

from components.finance_charts import change_text, fmt_value, history_chart, peer_bar, shap_waterfall
from components.finance_data_loader import CONTRACT_VERSION, PROVIDERS, aitu, forecast, missing, search, stage2_table
from components.styles import GLASS_CSS
from src.finance import aitu_profile
from src.finance import criterion_stage2 as C
from src.finance.api.contract import TARGET_META

st.set_page_config(page_title="Финансы вузов (бета) | EduForecast-SIS", page_icon="Ф", layout="wide",
                   initial_sidebar_state="expanded")
st.markdown(GLASS_CSS, unsafe_allow_html=True)
st.markdown("""
<style>
.beta-pill { display:inline-block; background:#d97706; color:#fff; font-size:0.68rem; font-weight:700;
             letter-spacing:0.08em; padding:3px 9px; border-radius:999px; vertical-align:middle; margin-left:10px; }
.beta-banner { background:#fffbeb; border:1px solid #fde68a; border-left:4px solid #d97706; border-radius:6px;
               padding:10px 14px; font-size:0.83rem; color:#78350f; margin:4px 0 18px 0; line-height:1.5; }
.mock-banner { background:#fef2f2; border:1px solid #fecaca; border-left:4px solid #dc2626; border-radius:6px;
               padding:10px 14px; font-size:0.83rem; color:#7f1d1d; margin:4px 0 18px 0; }
.inst-meta { font-size:0.82rem; color:#6b7280; margin-top:2px; }
.tag { display:inline-block; background:#eef2f7; color:#334155; font-size:0.72rem; padding:2px 8px;
       border-radius:4px; margin-right:6px; }
.flag-row { font-size:0.8rem; padding:6px 10px; border-radius:6px; margin-bottom:5px; border:1px solid #e3e6eb;
            background:#fff; }
.flag-info { border-left:3px solid #64748b; } .flag-warning { border-left:3px solid #d97706; }
.flag-critical { border-left:3px solid #dc2626; }
.sev { font-weight:700; font-size:0.66rem; letter-spacing:0.05em; margin-right:6px; }
.howto { background:#ffffff; border:1px solid #e3e6eb; border-radius:6px; padding:10px 16px; margin:0 0 16px 0;
         font-size:0.8rem; color:#334155; line-height:1.55; }
.howto b { color:#0f172a; }
.iv-note { font-size:0.74rem; color:#6b7280; margin:-6px 0 14px 0; }
.eval-banner { background:#eff6ff; border:1px solid #bfdbfe; border-left:4px solid #2563eb; border-radius:6px;
               padding:10px 14px; font-size:0.83rem; color:#1e3a8a; margin:4px 0 18px 0; line-height:1.5; }
.us-note { display:inline-block; background:#f1f5f9; color:#334155; font-size:0.74rem; font-weight:600;
           padding:3px 10px; border-radius:4px; margin:0 0 12px 0; }
.status-ok { color:#047857; font-weight:700; } .status-fail { color:#b91c1c; font-weight:700; }
</style>
""", unsafe_allow_html=True)

SEVERITY_LABEL = {"critical": "КРИТИЧНО", "warning": "ВНИМАНИЕ", "info": "ИНФО"}
CONTROL_LABEL = {"public": "государственный", "private_nonprofit": "частный некоммерческий"}

with st.sidebar:
    st.markdown("""
    <div style="padding:18px 0 16px 0; border-bottom:1px solid #1c2c4d; margin-bottom:14px;">
        <div style="font-size:1.05rem; font-weight:700; color:#f1f5f9;">EduForecast-SIS</div>
        <div style="font-size:0.68rem; color:#7d8db0; font-weight:500; margin-top:2px;">Модуль Finance · бета</div>
    </div>""", unsafe_allow_html=True)
    provider = st.radio("Источник прогноза", list(PROVIDERS), format_func=PROVIDERS.get, key="fin_provider")
    absent = missing(provider)
    choice = None
    if absent:
        st.caption("Нет данных для этого источника: " + ", ".join(p.name for p in absent))
    else:
        query = st.text_input("Поиск вуза", value=st.session_state.get("fin_query", "Ohio State"),
                              placeholder="Название, штат (OH) или UNITID", key="fin_query")
        hits = search(provider, query)
        if not hits and provider == "mock":
            st.caption("В мок-режиме реальных вузов нет — показан список мок-вузов")
            hits = search(provider, "")
        if not hits:
            st.caption("Ничего не найдено")
        else:
            by_id = {h["series_id"]: h for h in hits}
            choice_id = st.selectbox(
                "Результаты", list(by_id),
                format_func=lambda i: f"{by_id[i]['name']} ({by_id[i]['state']}, {by_id[i]['first_year']}–"
                                      f"{by_id[i]['last_year']})",
                key=f"fin_choice_{provider}")
            choice = by_id[choice_id]
    st.markdown(f"""
    <div style="margin-top:22px; padding-top:14px; border-top:1px solid #1c2c4d; font-size:0.68rem;
                color:#5b6b8c; line-height:1.9;">
        Данные: IPEDS 2010–2023<br>Деньги: CPI-U, $ FY2023<br>Контракт: {CONTRACT_VERSION}
    </div>""", unsafe_allow_html=True)

def forecast_tab():
    if choice is None:
        st.info("Нет данных для выбранного источника прогноза или вуз не найден. Данные: README, раздел «Подготовка данных → Finance (IPEDS)». Без данных работает мок-режим (переключатель в боковой панели) и вкладка «Профиль AITU».")
        return
    response, contract_errors = forecast(provider, int(choice["series_id"]))
    inst, prov = response["institution"], response["provider"]

    if prov["is_mock"]:
        st.markdown('<div class="mock-banner"><b>Мок-данные.</b> Все значения синтетические и нужны только для '
                    'проверки интерфейса. Не реальные вузы и не реальные прогнозы.</div>', unsafe_allow_html=True)
    elif prov["is_demo"]:
        st.markdown(f'<div class="beta-banner"><b>Бета-версия.</b> История — реальные данные IPEDS. Прогноз на '
                    f'{response["horizon_year"]} год даёт <b>демо-модель</b> ({prov["model_version"]}): обучена только на '
                    f'годах до 2019, гиперпараметры не подбирались, <b>по критерию успеха не оценивалась</b>. '
                    f'Не использовать для решений.</div>', unsafe_allow_html=True)
    else:
        status = {t: STATUS.get(t) for t in TARGET_META}
        ok = [TARGET_META[t]["label"] for t, v in status.items() if v is True]
        bad = [TARGET_META[t]["label"] for t, v in status.items() if v is False]
        st.markdown(f'<div class="eval-banner"><b>Модель оценена по зафиксированному критерию</b> (rolling origin '
                    f'2014–2022, выигрыш над naive ≥ 10% и 95% ДИ ниже нуля, в обеих оценках). '
                    f'Прошли критерий: <b>{", ".join(ok) or "ни один показатель"}</b>. '
                    f'Не прошли: <b>{", ".join(bad) or "нет"}</b> — по ним прогноз не лучше «как в прошлом году». '
                    f'Подробности на вкладке «Качество моделей».</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="howto"><b>Как читать страницу</b><br>
    <b>Прогноз</b> — оценка показателя на следующий год от модели (синяя точка на графике).<br>
    <b>Интервал</b> — диапазон, в который реальное значение должно попадать примерно в 80% случаев (синяя полоса).<br>
    <b>Baseline</b> — простые ориентиры для сравнения: «как в прошлом году» (naive) и «прошлый год плюс средний рост похожих вузов».<br>
    <b>SHAP</b> — какие признаки вуза подняли или опустили прогноз и насколько.<br>
    <b>Флаги</b> — предупреждения о качестве данных: COVID-годы, смена отчётности в 2018, слияния и смена UNITID, малые когорты, аномальные скачки.
    </div>""", unsafe_allow_html=True)
    IV_NOTE = ("Интервал синтетический (мок)." if prov["is_mock"] else
               "Интервал одинаковой ширины для всех вузов, калиброван на 2018 году; это демо-оценка." if prov["is_demo"]
               else "Интервал 80%: split conformal, ширина зависит от исторической волатильности ряда; эмпирическое "
                    "покрытие в проверке 2015–2023 — на вкладке «Качество моделей».")
    MODEL_NAME = "Мок" if prov["is_mock"] else "Демо-модель" if prov["is_demo"] else "Модель этапа 2"

    if contract_errors:
        st.error("Ответ не соответствует контракту: " + "; ".join(contract_errors[:3]))

    st.markdown(f"""
    <div class="glass-card" style="padding:16px 20px;">
      <div style="font-size:1.25rem; font-weight:700; color:#0f172a;">{inst['name']}</div>
      <div class="inst-meta">
        <span class="tag">{inst['state']}</span><span class="tag">{CONTROL_LABEL.get(inst['control'], inst['control'])}</span>
        <span class="tag">Carnegie: {inst['carnegie_group']}</span><span class="tag">UNITID {inst['unitid']}</span>
        <span class="tag">Группа сравнения: {inst['peer_group']}</span>
      </div>
    </div>""", unsafe_allow_html=True)

    targets = {t["target"]: t for t in response["targets"]}
    cols = st.columns(len(targets))
    for col, t in zip(cols, targets.values()):
        last = next((p for p in reversed(t["history"]) if p["value"] is not None), None)
        fc = t["forecast"]
        if fc:
            delta = (f'Прогноз {fc["year"]}: <b>{fmt_value(fc["value"], t["unit"])}</b> '
                     f'({change_text(fc["predicted_change"], t["change_scale"])})<br>'
                     f'{int(fc["interval"]["level"] * 100)}%: {fmt_value(fc["interval"]["lower"], t["unit"])} – '
                     f'{fmt_value(fc["interval"]["upper"], t["unit"])}')
            accent = ""
        else:
            delta, accent = f'Прогноз не строится: {t["ineligible_reason"]}', " accent-amber"
        if not prov["is_demo"] and STATUS.get(t["target"]) is not None:
            passed = STATUS[t["target"]]
            delta += (f'<br><span class="{"status-ok" if passed else "status-fail"}">Критерий: '
                      f'{"прошла" if passed else "не прошла"}</span>')
        with col:
            st.markdown(f"""
            <div class="metric-card{accent}">
              <div class="metric-label">{t['label']}{f" · {last['year']}" if last else ""}</div>
              <div class="metric-value" style="font-size:1.55rem;">{fmt_value(last['value'] if last else None, t['unit'])}</div>
              <div class="metric-delta" style="color:#475569; line-height:1.5;">{delta}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown(f'<div class="iv-note" style="margin-top:8px;">{IV_NOTE}</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-title">История и прогноз</div>', unsafe_allow_html=True)
    selected = st.radio("Показатель", list(targets), format_func=lambda k: targets[k]["label"], horizontal=True,
                        key="fin_target", label_visibility="collapsed")
    block = targets[selected]

    left, right = st.columns([2.2, 1])
    with left:
        label = f"Прогноз ({MODEL_NAME.lower()})"
        st.plotly_chart(history_chart(block, f"{block['label']}, {block['unit']}", label), width="stretch",
                        config={"displayModeBar": False})
    with right:
        st.markdown("**Прогноз и baseline**")
        rows = []
        if block["forecast"]:
            rows.append((MODEL_NAME, block["forecast"]["value"]))
        names = {"naive": "Naive (как в прошлом году)", "peer_group_mean_growth": "Средний рост группы"}
        rows += [(names[b["name"]], b["value"]) for b in block["baselines"]]
        if rows:
            st.dataframe(pd.DataFrame([(n, fmt_value(v, block["unit"])) for n, v in rows], columns=["", "Значение"]),
                         hide_index=True, width="stretch")
            if block["forecast"]:
                iv = block["forecast"]["interval"]
                st.caption(f"Интервал {int(iv['level'] * 100)}%: {fmt_value(iv['lower'], block['unit'])} – "
                           f"{fmt_value(iv['upper'], block['unit'])}. {IV_NOTE}".replace("$", "\\$"))
        else:
            st.caption(block["ineligible_reason"])
        st.markdown("**Флаги качества данных**")
        target_flags = [f for f in response["data_quality"]["flags"] if f["target"] in (selected, None)]
        grouped = {}
        for f in target_flags:
            grouped.setdefault((f["code"], f["severity"], f["message"]), []).append(f["year"])
        for (code, sev, msg), years in sorted(grouped.items(), key=lambda kv: ["critical", "warning", "info"].index(kv[0][1])):
            ys = ", ".join(str(y) for y in sorted({y for y in years if y}))
            st.markdown(f'<div class="flag-row flag-{sev}"><span class="sev">{SEVERITY_LABEL[sev]}</span>{msg}'
                        f'{f" — {ys}" if ys else ""}</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-title">Почему такой прогноз: вклад признаков (SHAP)</div>', unsafe_allow_html=True)
    if block["explanation"]:
        ex = block["explanation"]
        units = ("процентных пунктах (п.п.)" if ex["scale"] == "percentage_points" else
                 "процентах роста за год (приближённо)")
        st.caption(
            "Как читать: модель прогнозирует, на сколько показатель изменится за год. Нижний синий столбик — "
            "среднее изменение по всем вузам в обучающих данных; каждый следующий столбик — один признак этого вуза: "
            "зелёный поднимает прогноз, красный опускает, длина — насколько. Верхний синий столбик — итоговый прогноз "
            f"изменения ({change_text(ex['prediction'], ex['scale'])}). Значения на столбиках — в {units}. "
            f"Метод: {ex['method']}.")
        st.plotly_chart(shap_waterfall(ex), width="stretch", config={"displayModeBar": False})
    else:
        st.info(f"Для этого показателя прогноз не строится: {block['ineligible_reason']}")

    st.markdown('<div class="section-title">Сравнение с похожими вузами</div>', unsafe_allow_html=True)
    st.caption("5 ближайших вузов той же группы (тип × Carnegie) по размеру, расходам на FTE, retention, выпускаемости "
               "и доле расходов на преподавание в последнем году.")
    peers = response["peers"]
    c1, c2 = st.columns([1.2, 1])
    with c1:
        last = next((p for p in reversed(block["history"]) if p["value"] is not None), None)
        bars = [(inst["name"], last["value"] if last else None, True)] + [(p["name"], p["latest"].get(selected), False)
                                                                           for p in peers]
        st.plotly_chart(peer_bar(bars, block["unit"], f"{block['label']}, последний год"), width="stretch",
                        config={"displayModeBar": False})
    with c2:
        table = pd.DataFrame([{"Вуз": p["name"], "Штат": p["state"],
                               block["label"]: fmt_value(p["latest"].get(selected), block["unit"]),
                               "Дистанция": round(p["distance"], 2)} for p in peers])
        st.dataframe(table, hide_index=True, width="stretch")

    with st.expander(f"Ответ API (контракт {response['contract_version']})"):
        st.caption(f"Провайдер: {prov['name']} · модель {prov['model_version']} · обучена до {prov['trained_through_year']} · "
                   f"оценка по критерию: {'да' if prov['evaluated_against_criterion'] else 'нет'} · "
                   f"проверка схемы: {'OK' if not contract_errors else 'ошибки'}")
        payload = json.dumps(response, ensure_ascii=False, indent=2)
        st.download_button("Скачать JSON", payload, file_name=f"forecast_{inst['unitid']}.json", mime="application/json")
        st.code(payload[:6000] + ("\n..." if len(payload) > 6000 else ""), language="json")


PRIMARY = f"{C.PRIMARY[0]}_{C.PRIMARY[1]}"
MODEL_LABELS = {"constant": "Константа (средний рост панели)", "ridge_S1": "Ridge S1", "ridge_S2": "Ridge S2",
                "ridge_S3": "Ridge S3", "lgbm_S1": "LightGBM S1", "lgbm_S2": "LightGBM S2",
                "lgbm_S3": "LightGBM S3 (основная)"}
SCOPE_LABELS = {"all_years": "все годы", "excluding_flagged": "без помеченных"}
CRIT = stage2_table("criterion_rolling.csv")
STATUS = ({t: bool(g["meets_success_rule"].all()) for t, g in CRIT[CRIT["model"] == PRIMARY].groupby("target")}
          if CRIT is not None else {})
US_NOTE = '<span class="us-note">Данные США (IPEDS), контекст другой</span>'


def pct(x):
    return "—" if pd.isna(x) else f"{x * 100:+.1f}%"


def quality_tab():
    st.markdown(US_NOTE, unsafe_allow_html=True)
    if CRIT is None:
        st.info("Результаты этапа 3 не найдены. Команды: `python -m src.finance.models_stage2 rolling`, "
                "`... unseen`, `... report` (см. FINANCE_STAGE2_REPORT.md).")
        return
    st.markdown("**Критерий успеха** (зафиксирован до моделей, `src/finance/criterion.py`): MAE модели хотя бы на "
                "10% ниже naive («как в прошлом году») и 95% bootstrap-ДИ разницы по вузам целиком ниже нуля — "
                "в обеих оценках: по всем годам и без помеченных (COVID, GASB 75, смена UNITID).")
    p = CRIT[CRIT["model"] == PRIMARY]
    rows = []
    for t in TARGET_META:
        g = p[p["target"] == t].set_index("scope")
        if g.empty:
            continue
        rows.append({"Показатель": TARGET_META[t]["label"],
                     **{f"Выигрыш, {SCOPE_LABELS[s]}": pct(g.at[s, "gain_vs_naive"]) for s in g.index},
                     **{f"95% ДИ разницы, {SCOPE_LABELS[s]}": f"[{g.at[s, 'diff_ci_lo']:.4f}; {g.at[s, 'diff_ci_hi']:.4f}]"
                        for s in g.index},
                     "Критерий": "прошла" if g["meets_success_rule"].all() else "не прошла"})
    st.markdown("**Основная модель (LightGBM S3), rolling origin 2014–2022**")
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

    st.markdown("**Абляция наборов признаков** — выигрыш над naive, все годы / без помеченных")
    ab = CRIT.pivot_table(index="model", columns=["target", "scope"], values="gain_vs_naive")
    ab = ab.reindex([m for m in MODEL_LABELS if m in ab.index])
    show = pd.DataFrame({TARGET_META[t]["label"]: [f"{pct(ab.at[m, (t, 'all_years')])} / "
                                                   f"{pct(ab.at[m, (t, 'excluding_flagged')])}" for m in ab.index]
                         for t in TARGET_META if (t, "all_years") in ab.columns}, index=[MODEL_LABELS[m] for m in ab.index])
    st.dataframe(show, width="stretch")
    st.caption("S1 — лаги цели, размер, сектор, Carnegie; S2 — S1 + структура расходов; S3 — S2 + селективность, "
               "Pell, цена, помощь, кадры, профиль программ.")

    uns = stage2_table("criterion_unseen_summary.csv")
    if uns is not None:
        u = uns[uns["model"] == PRIMARY]
        st.markdown("**Вузы, которых модель не видела** (origin 2016, 2019, 2022; 5 разбиений, 20% рядов вне обучения)")
        st.dataframe(pd.DataFrame([{"Показатель": TARGET_META[r.target]["label"], "Оценка": SCOPE_LABELS[r.scope],
                                    "Разбиений прошло критерий": f"{int(r.splits_passing)} из 5",
                                    "Выигрыш (среднее, мин–макс)": f"{pct(r.gain_mean)} ({pct(r.gain_min)} … {pct(r.gain_max)})"}
                                   for r in u.itertuples()]), hide_index=True, width="stretch")

    cov = stage2_table("interval_coverage.csv")
    if cov is not None:
        st.markdown(f"**Покрытие 80%-интервалов** (номинал {C.INTERVAL_LEVEL:.0%})")
        cov = cov.assign(Показатель=cov["target"].map(lambda t: TARGET_META[t]["label"]))
        st.dataframe(cov.pivot_table(index=["breakdown", "group"], columns="Показатель", values="coverage")
                     .map(lambda v: f"{v:.0%}"), width="stretch")

    imp = stage2_table("shap_importance.csv")
    if imp is not None:
        st.markdown("**Главные признаки основной модели** (средний |SHAP|, модель на origin 2022)")
        cols = st.columns(len(TARGET_META))
        for col, t in zip(cols, TARGET_META):
            top = imp[imp["target"] == t].nlargest(6, "mean_abs_shap")
            with col:
                st.caption(TARGET_META[t]["label"])
                st.dataframe(top[["feature", "mean_abs_shap"]].rename(
                    columns={"feature": "признак", "mean_abs_shap": "|SHAP|"}).round(4), hide_index=True)


def aitu_tab():
    data = aitu()
    st.markdown('<div class="beta-banner"><b>Профиль AITU по отчётности за 2020 год.</b> '
                + " ".join(aitu_profile.CAVEATS) + '</div>', unsafe_allow_html=True)
    s = data["structure"]
    money = {"revenue_per_employee_thousand_kzt", "equity"}
    table = pd.DataFrame({str(y): [(f"{v:,.0f}" if k in money else f"{v:.3f}" if k in ("current_ratio", "liabilities_to_assets")
                                    else f"{v:.1%}") if pd.notna(v) else "—" for k, v in s.loc[y].items()]
                          for y in s.index}, index=[aitu_profile.LABELS[k] for k in s.columns])
    st.markdown("**Структурные показатели** (доли — от итога доходов или расходов)")
    st.dataframe(table, width="stretch")

    st.markdown("**Флаги правил** (порог допускается только с источником; `src/finance/rules.yaml`)")
    r = data["rules"]
    show = r[r["year"] == r["year"].max()][["label", "value", "threshold", "triggered", "message", "source", "status",
                                             "caveat"]]
    show = show.assign(triggered=show["triggered"].map({True: "сработал", False: "нет", None: "не рассчитан"}))
    st.dataframe(show.rename(columns={"label": "правило", "value": "значение", "threshold": "порог",
                                      "triggered": "флаг", "message": "сообщение", "source": "источник",
                                      "status": "статус", "caveat": "оговорка"}), hide_index=True, width="stretch")
    if not data["us_data"]:
        st.caption("Сравнение с аналогами США не рассчитано: нет панели IPEDS (`data/finance/panel_stage2.parquet`).")
    st.caption("Сравнение с вузами США — только по структурным долям (оплата труда, амортизация), не по суммам "
               "в тенге. Ориентир США, контекст другой.")
    with st.expander("Проверки сумм"):
        st.dataframe(data["checks"], hide_index=True, width="stretch")


def link_tab():
    st.markdown(US_NOTE, unsafe_allow_html=True)
    st.markdown("**Это связь, не причина.** Двусторонняя модель с фиксированными эффектами вуза и года на "
                "первых разностях: как изменение доли расходов на функцию связано с изменением результата в том же "
                "году. Гипотезы и спецификация зафиксированы до расчёта (`src/finance/criterion_stage2.py`). "
                "Наблюдательные данные не позволяют говорить об эффекте: доли меняются вместе с другими решениями вуза.")
    h = stage2_table("hypotheses.csv")
    if h is None:
        st.info("Результаты не найдены: `python -m src.finance.budget_outcomes`.")
        return
    names = {"H1": "H1: доля студенческих сервисов → retention (+)", "H2": "H2: доля преподавания → выпускаемость (+)",
             "H3": "H3: доля академической поддержки → retention (+)",
             "H4": "H4: доля институциональной поддержки → выпускаемость (−)"}
    main = h[h["spec"] == "main"]
    st.dataframe(pd.DataFrame([{"Гипотеза": names[r.hypothesis],
                                "Связь, п.п. результата на +1 п.п. доли": f"{r.beta:+.3f}",
                                "95% ДИ": f"[{r.ci_lo:+.3f}; {r.ci_hi:+.3f}]", "p": f"{r.p:.3f}",
                                "p (Холм)": f"{r.p_holm:.3f}", "наблюдений / вузов": f"{r.n_obs:,} / {r.n_series:,}",
                                "вывод": r.verdict} for r in main.itertuples()]), hide_index=True, width="stretch")
    pl = h[h["spec"] == "placebo_lead"]
    st.caption("Плацебо (изменение доли в следующем году не должно «объяснять» результат текущего): "
               + "; ".join(f"{r.hypothesis}: p = {r.p:.2f}" for r in pl.itertuples()))
    with st.expander("Чувствительность (лаг, без COVID, публичные/частные, без винсоризации, с контролями)"):
        st.dataframe(h[~h["spec"].isin(["main", "placebo_lead"])][
            ["hypothesis", "spec", "beta", "ci_lo", "ci_hi", "p", "p_holm", "n_obs", "verdict"]].round(4),
            hide_index=True, width="stretch")


pill = '<span class="beta-pill">БЕТА</span>' if provider != "stage2" else ""
st.markdown(f'<h1 style="margin:0; font-size:1.7rem;">Финансы и результаты вузов{pill}</h1>', unsafe_allow_html=True)
tab_fc, tab_q, tab_aitu, tab_link = st.tabs(["Прогноз вуза", "Качество моделей", "Профиль AITU",
                                             "Связь бюджета и результатов (связь, не причина)"])
with tab_fc:
    st.markdown(US_NOTE, unsafe_allow_html=True)
    forecast_tab()
with tab_q:
    quality_tab()
with tab_aitu:
    aitu_tab()
with tab_link:
    link_tab()
