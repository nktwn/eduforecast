import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import streamlit as st

from components.finance_charts import change_text, fmt_value, history_chart, peer_bar, shap_waterfall
from components.finance_data_loader import CONTRACT_VERSION, PROVIDERS, forecast, search
from components.styles import GLASS_CSS, require_data
from src.finance.api.demo_model import META_PATH
from src.finance.config import PANEL_PATH

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
if provider == "demo":
    require_data([PANEL_PATH, META_PATH], "Подготовка данных → Finance (IPEDS)",
                 "Без данных можно открыть мок-режим: переключатель «Мок (синтетика)» в боковой панели.")
with st.sidebar:
    query = st.text_input("Поиск вуза", value=st.session_state.get("fin_query", "Ohio State"),
                          placeholder="Название, штат (OH) или UNITID", key="fin_query")
    hits = search(provider, query)
    if not hits and provider == "mock":
        st.caption("В мок-режиме реальных вузов нет — показан список мок-вузов")
        hits = search(provider, "")
    if not hits:
        st.caption("Ничего не найдено")
        st.stop()
    by_id = {h["series_id"]: h for h in hits}
    choice_id = st.selectbox(
        "Результаты", list(by_id),
        format_func=lambda i: f"{by_id[i]['name']} ({by_id[i]['state']}, {by_id[i]['first_year']}–{by_id[i]['last_year']})",
        key=f"fin_choice_{provider}")
    choice = by_id[choice_id]
    st.markdown(f"""
    <div style="margin-top:22px; padding-top:14px; border-top:1px solid #1c2c4d; font-size:0.68rem;
                color:#5b6b8c; line-height:1.9;">
        Данные: IPEDS 2010–2023<br>Деньги: CPI-U, $ FY2023<br>Контракт: {CONTRACT_VERSION}
    </div>""", unsafe_allow_html=True)

response, contract_errors = forecast(provider, int(choice["series_id"]))
inst, prov = response["institution"], response["provider"]

st.markdown('<h1 style="margin:0; font-size:1.7rem;">Финансы и результаты вуза<span class="beta-pill">БЕТА</span></h1>',
            unsafe_allow_html=True)
if prov["is_mock"]:
    st.markdown('<div class="mock-banner"><b>Мок-данные.</b> Все значения синтетические и нужны только для '
                'проверки интерфейса. Не реальные вузы и не реальные прогнозы.</div>', unsafe_allow_html=True)
else:
    st.markdown(f'<div class="beta-banner"><b>Бета-версия.</b> История — реальные данные IPEDS. Прогноз на '
                f'{response["horizon_year"]} год даёт <b>демо-модель</b> ({prov["model_version"]}): обучена только на '
                f'годах до 2019, гиперпараметры не подбирались, <b>по критерию успеха не оценивалась</b>. '
                f'Не использовать для решений.</div>', unsafe_allow_html=True)
st.markdown("""
<div class="howto"><b>Как читать страницу</b><br>
<b>Прогноз</b> — оценка показателя на следующий год от модели (синяя точка на графике).<br>
<b>Интервал</b> — диапазон, в который реальное значение должно попадать примерно в 80% случаев (синяя полоса).<br>
<b>Baseline</b> — простые ориентиры для сравнения: «как в прошлом году» (naive) и «прошлый год плюс средний рост похожих вузов».<br>
<b>SHAP</b> — какие признаки вуза подняли или опустили прогноз и насколько.<br>
<b>Флаги</b> — предупреждения о качестве данных: COVID-годы, смена отчётности в 2018, слияния и смена UNITID, малые когорты, аномальные скачки.
</div>""", unsafe_allow_html=True)
IV_NOTE = ("Интервал синтетический (мок)." if prov["is_mock"] else
           "Интервал одинаковой ширины для всех вузов, калиброван на 2018 году; это демо-оценка.")

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
    label = "Прогноз (мок)" if prov["is_mock"] else "Прогноз (демо-модель)"
    st.plotly_chart(history_chart(block, f"{block['label']}, {block['unit']}", label), width="stretch",
                    config={"displayModeBar": False})
with right:
    st.markdown("**Прогноз и baseline**")
    rows = []
    if block["forecast"]:
        rows.append(("Демо-модель", block["forecast"]["value"]))
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
