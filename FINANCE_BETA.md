# FINANCE_BETA.md — модуль Finance, этап B: бета интерфейса

Дата: 2026-10-09. Страница `app/pages/05_Finance.py` (Streamlit), API-слой `src/finance/api/`.
Запуск: `streamlit run app/main.py` → раздел **Finance**. Нужны локальные `data/finance/panel.parquet` и `data/finance/models/` (не в git, см. §5).

> **Бета.** История на графиках — реальные данные IPEDS. Прогнозы делает **демо-модель** LightGBM, обученная только на годах до 2019. **По зафиксированному критерию успеха (`src/finance/criterion.py`) она не оценивалась** и отношения к будущему этапу моделей не имеет. Режим «Мок» показывает только синтетику.

## 1. JSON-контракт API

- **Версия:** `finance-forecast/0.1.0`.
- **Схема:** `src/finance/api/forecast_response.schema.json` (JSON Schema draft 2020-12, `additionalProperties: false` на всех уровнях).
- **Проверка:** `src/finance/api/contract.py::validate()`. Проверены все 2 185 рядов панели в демо-режиме и мок-ответы: 0 ошибок.

Ответ соответствует запросу `GET /finance/v0/institutions/{unitid}/forecast`: один вуз, все цели, горизонт — следующий год.

| блок | содержимое |
|---|---|
| `provider` | `name` (`mock` / `demo-lightgbm`), **`is_mock`**, **`is_demo`**, `model_version`, `trained_through_year`, **`evaluated_against_criterion`** (сейчас всегда `false`), `notes` |
| `institution` | `unitid`, `series_id` (склеенный ряд, см. F1), название, штат, тип, Carnegie, группа сравнения |
| `data_vintage` | источник, первый и последний год, база цен (CPI-U, $ FY2023) |
| `targets[]` | по одной записи на цель: `retention_rate`, `grad_rate_150`, `fall_enrollment`, `core_total_per_fte_real` |
| `targets[].history[]` | `{year, value, flags[]}` — история с кодами флагов по точкам |
| `targets[].forecast` | `{year, value, predicted_change, interval: {level, lower, upper, method}}` или `null`, если прогноз не строится |
| `targets[].eligible` / `ineligible_reason` | допуск к прогнозу (правила F1: бакалавриат и когорта ≥ 30; ряд не оборван) |
| `targets[].baselines[]` | `naive`, `peer_group_mean_growth` |
| `targets[].explanation` | `{method, scale, base_value, prediction, contributions[{feature, label, feature_value, contribution}]}`; сумма `base_value + Σ contribution = prediction` (шкала изменения: п.п. или логарифм отношения) |
| `targets[].peer_median_history[]` | медиана 5 похожих вузов по годам |
| `peers[]` | 5 ближайших вузов: `unitid`, название, штат, `distance`, последние значения целей |
| `data_quality.flags[]` | `{code, severity, message, year, target}` |

**Коды флагов** (`severity`):

| код | уровень | смысл |
|---|---|---|
| `MOCK_DATA` | critical | синтетические данные |
| `DEMO_MODEL` | warning | демо-модель, по критерию не оценивалась |
| `ID_TRANSITION` / `MERGER_ABSORPTION` | warning | смена UNITID или отчётности; поглощение другого вуза |
| `NOT_ELIGIBLE` | warning | цель не прогнозируется |
| `OUTLIER_CHANGE` | warning | изменение за год > 20 п.п. или > 0.5 по логарифму |
| `FINANCE_PARTIAL` | warning | частичная финансовая отчётность |
| `SHORT_HISTORY` | warning | меньше 5 лет истории |
| `COVID_YEAR` | info | 2020–2022 |
| `GASB75_2018` | info | государственный вуз, 2018 год, расходы |
| `SMALL_COHORT` | info | когорта < 30 |
| `FINANCE_PARENT_CHILD` | info | финансы включают дочерние кампусы |
| `MISSING_VALUE` | info | значение за год отсутствует |

**Пример фрагмента** (Ohio State, retention):

```json
{
  "provider": {"name": "demo-lightgbm", "is_mock": false, "is_demo": true, "model_version": "demo-lgbm-0.1",
               "trained_through_year": 2018, "evaluated_against_criterion": false},
  "targets": [{
    "target": "retention_rate",
    "forecast": {"year": 2024, "value": 94.18, "predicted_change": 0.18,
                 "interval": {"level": 0.8, "lower": 89.31, "upper": 99.06, "method": "split conformal (|остаток| на 2018 году)"}},
    "baselines": [{"name": "naive", "value": 94.0}, {"name": "peer_group_mean_growth", "value": 94.59}],
    "explanation": {"method": "TreeSHAP (LightGBM pred_contrib)", "scale": "percentage_points",
                    "base_value": 0.213, "prediction": 0.181,
                    "contributions": [{"feature": "retention_level", "label": "Retention (текущий год)",
                                       "feature_value": 94.0, "contribution": -1.136}]}
  }]
}
```

Полный ответ для любого вуза: `python -m src.finance.api.cli "<название или UNITID>" [--provider mock]`. Команда печатает JSON и завершается с ошибкой, если ответ не проходит схему.

## 2. Провайдеры

Оба реализуют один интерфейс `Provider` (`search(query)`, `forecast(series_id)`) и отдают ответ по контракту. Страница не знает, какой провайдер работает: переключатель в сайдбаре.

| провайдер | данные | прогноз | интервал | SHAP |
|---|---|---|---|---|
| `MockProvider` | 10 синтетических «Mock University N», детерминированно по `series_id` | случайное изменение | ±2σ | случайные вклады, сумма совпадает с прогнозом |
| `DemoProvider` | реальная панель IPEDS 2010–2023 (`FinanceRepository`) | демо-LightGBM | split conformal 80% | TreeSHAP из LightGBM (`pred_contrib`) |

**Демо-модель** (`src/finance/api/demo_model.py`, версия `demo-lgbm-0.1`):
- **Цель:** изменение показателя за год (п.п. или логарифм отношения), отдельная модель на каждую из 4 целей.
- **Признаки** (18, `features.py`): тип контроля, Carnegie, размер, core-расходы на FTE, структура расходов, доля валовых стипендий, FTE на преподавателя, текущие retention и выпускаемость, рост приёма и расходов, уровень цели, два лага изменения, средний рост группы. Один и тот же код признаков используется при обучении и при прогнозе.
- **Обучение:** целевые годы ≤ 2017, 9–12 тыс. строк на цель. **Калибровка интервала:** целевой 2018 год. Данные 2019+ модель не видела.
- **Гиперпараметры** фиксированные, без подбора: L1-loss, 300 деревьев, 15 листьев, `min_child_samples` 40.
- **Полуширина 80%-интервала:** retention ±4.9 п.п., выпускаемость ±4.7 п.п., приём ±8% (0.079 по логарифму), core-расходы ±11% (0.105).
- **Оценка:** точность демо-модели **не измерялась** ни по критерию, ни отдельно. Это сознательно: она нужна только чтобы наполнить интерфейс, а оценка моделей — следующий этап по зафиксированному протоколу.
- Метаданные: `data/finance/models/demo_meta.json` (`is_demo: true`, `evaluated_against_criterion: false`).

## 3. Экраны

Скриншоты (Playwright, Chromium, 1440 px) лежат в `docs/finance_beta/`.

| файл | что показано |
|---|---|
| `01_card_full_ohio_state.png` | вся страница вуза целиком |
| `02_card_top_ohio_state.png` | плашка «БЕТА» и баннер, сайдбар с поиском и выбором провайдера, карточка вуза, 4 KPI (последний год, прогноз 2024, 80%-интервал), график retention с полосой COVID, прогнозом и baseline, флаги |
| `03_search_and_flags_kennesaw.png` | поиск («Kennesaw»: в результатах два UNITID с годами ряда), приём: смена UNITID в 2015 году (красный крест и пунктир), флаг ID_TRANSITION |
| `04_expenses_flags_umich.png` | core-расходы на FTE в $ FY2023: маркер GASB 75 (2018), полоса COVID, медиана похожих вузов, интервал и baseline |
| `05_shap_waterfall_ohio_state.png` | SHAP-waterfall: от среднего изменения по выборке через 8 главных признаков (и «остальные») к прогнозу изменения |
| `06_peers_ohio_state.png` | сравнение с 5 похожими вузами: столбцы (выбранный вуз выделен) и таблица |
| `07_not_eligible_rockefeller.png` | вуз без бакалавриата: KPI «прогноз не строится», маркеры аномальных изменений в расходах |
| `08_mock_mode.png` | мок-режим: красный баннер, флаг MOCK_DATA (critical), синтетические ряды |
| `09_alias_search_ucla.png` | поиск по аббревиатуре «UCLA», блок «Как читать страницу», подпись про ширину интервала |

Внизу страницы — раскрывающийся блок «Ответ API» с полным JSON, результатом проверки схемы и кнопкой скачивания.

## 4. Что в бете ещё мок или упрощено

1. **Прогнозы — демо-модель, не результат.** Модель не оценена ни по критерию, ни вообще. Гиперпараметры не подбирались. Данные после 2018 года не использованы, хотя на дворе 2023.
2. **Режим «Мок» полностью синтетический:** вузы, ряды, прогнозы, интервалы и SHAP-вклады. Похожие вузы в моке без значений.
3. **HTTP API нет.** Контракт описан и проверяется, но страница вызывает провайдер в том же процессе. Сервер (FastAPI или аналог), версионирование URL, авторизация, rate limit не сделаны.
4. **Интервалы упрощены.** Split conformal на одном калибровочном годе (2018), одна ширина для всех вузов: не зависит от размера вуза и волатильности ряда, не учитывает COVID-годы. Покрытие не проверялось.
5. **Похожие вузы** — простой kNN по 5 стандартизованным показателям последнего года внутри группы «тип × Carnegie». Веса не подобраны, без учёта динамики и географии.
6. ~~Средний рост группы считается отдельным кодом~~ — исправлено: страница вызывает `src/finance/baseline.py::latest_group_changes`, тот же расчёт, что в `predictions()`. Совпадение проверяет `tests/test_finance_group_baseline.py` (`python -m tests.test_finance_group_baseline`).
7. **Горизонт** — только следующий год (2024). Сценариев «что если» и многолетнего прогноза нет.
8. **Данные — статичный снимок IPEDS** от 2026-10-09. Обновления, планировщика и проверки свежести нет. FY2024 ещё не опубликован.
9. **Поиск** — подстрока по названию, код штата, UNITID и словарь из 34 аббревиатур (`providers.py::ALIASES`: UCLA, MIT, NYU, USC, UNC, UVA, UIUC, UT Austin и др.). Нечёткого поиска нет; аббревиатуры вне словаря не находятся.
10. **Подписи признаков в SHAP** на русском захардкожены в `features.py`, локализации нет. SHAP показан на шкале изменения, а не уровня.
11. **Тестов** UI и провайдеров нет. Есть только проверка схемы на всех вузах (§1) и прогон сценариев Playwright для скриншотов.
12. **Модели и панель не в git.** Нужно воспроизвести (§5). Хранилища артефактов (model registry) нет.

## 5. Воспроизведение

```bash
python -m src.finance.download         # IPEDS + CPI-U (~1.1 ГБ)
python -m src.finance.panel            # панель
python -m src.finance.api.demo_model   # демо-модели → data/finance/models/
python -m src.finance.api.cli "Ohio State"   # проверка контракта
streamlit run app/main.py              # → Finance
```
