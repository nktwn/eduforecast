# PROJECT_STATUS.md — EduForecast-SIS

Аудит проведён: 2026-10-01. Репозиторий: `eduforecast` (ветка `main`, 1 коммит, git user `NurkhatSergaziyev`).

> ⚠️ **Важно про git:** в индексе git сейчас только 24 файла — `README.md`, `data/README.md`, `requirements.txt`, `setup.py`, весь `src/` и 12 ноутбуков. **Вся директория `app/` (весь Streamlit-дашборд) не закоммичена** (`git status` → `?? app/`), как и `data/raw`, `data/processed`, `results/` (в `.gitignore`). Если дашборд нужно сохранить в истории — его надо явно `git add`.

---

## 1. Дерево структуры проекта

```
eduforecast/
├── README.md                         # питч проекта, инструкция установки, таблица моделей (RF/LSTM/TFT) — НЕ обновлён после добавления app/
├── requirements.txt                  # есть незакоммиченная локальная правка (блок "Streamlit App")
├── setup.py                          # пакет eduforecast 0.1.0, python>=3.10, extras_require={"tft": [...]}
├── data/
│   ├── README.md                     # инструкция по скачиванию OULAD, список 7 CSV
│   ├── raw/                          # НЕ в git; 7 исходных CSV OULAD (studentVle.csv — 10.6M строк)
│   └── processed/                    # НЕ в git; static/sequential фичи + train/test сплиты
├── notebooks/                        # 12 файлов (6 исходных + 6 *_executed), все в git
│   ├── 01_eda(.ipynb / _executed.ipynb)
│   ├── 02_features(...)
│   ├── 03_baseline(...)
│   ├── 04_lstm(...)
│   ├── 05_tft(...)
│   └── 06_shap(...)
├── src/                              # "чистая" библиотека — в git, но НЕ используется пайплайном (см. §2.7)
│   ├── config.py, data_loader.py, features.py, models.py, evaluate.py, visualize.py
├── app/                              # Streamlit-приложение — НЕ в git
│   ├── main.py                       # главная страница дашборда
│   ├── pages/
│   │   ├── 01_Students.py
│   │   ├── 02_Analytics.py
│   │   └── 03_AI_Advisor.py
│   └── components/
│       ├── data_loader.py            # загрузка данных + обучение модели + SHAP для приложения
│       ├── charts.py                 # все Plotly-графики
│       └── styles.py                 # CSS-тема + sidebar
└── results/                          # НЕ в git; веса моделей, метрики, фигуры, final_report.md
    ├── final_report.md
    ├── lstm_best_model.pth / tft_best_model.pth
    ├── figures/ (31 PNG)
    └── metrics/ (9 CSV)
```

---

## 2. Реализованный модуль Academic (Student Retention & Early Warning)

### 2.1 Загрузка / обработка данных OULAD

Две **независимые, не связанные между собой** реализации:

- **`src/data_loader.py` → `DataLoader`** — используется только (условно) ноутбуками; методы `load_student_info()`, `load_student_registration()`, `load_student_vle()`, `load_assessments()`, `load_student_assessment()`, `load_courses()`, `load_vle()`, `load_all()`. Ожидает 7 CSV в `data/raw/` (все присутствуют локально).
- **`app/components/data_loader.py::load_raw_data()`** — отдельный, `@st.cache_data`-обёрнутый загрузчик, читает 5 из 7 CSV напрямую с явными dtype для `studentVle.csv`.

Предобработка (null-handling, очистка) выполняется **инлайн внутри ноутбуков**, а не в `src/` — конкретно в `notebooks/02_features(_executed).ipynb` (например, `dropna` по `date` в `assessments.csv` — 11 строк без даты экзамена).

### 2.2 Feature Engineering

Снова две параллельные реализации:

- **`src/features.py` → `FeatureEngineer`** — определён, но **не импортируется ни одним ноутбуком и не используется приложением** (мёртвый код). Методы: `create_weekly_clicks`, `create_target_variable` (`is_at_risk` = `final_result == "Withdrawn"`), `create_static_features` (label-encoding демографии), `create_assessment_features`, `build_feature_matrix`.
- **Фактическая фиче-инженерия, которая реально породила `data/processed/*.csv`** — в `notebooks/02_features_executed.ipynb`:
  - Демография/статика: `gender`, `disability` (бинарные), `highest_education`, `age_band` (ординальные), `imd_band`, `region`, `num_of_prev_attempts`, `studied_credits`
  - VLE-агрегаты: `total_clicks`, `active_weeks`, `max_weekly_clicks`, `mean_weekly_clicks`, `first_active_week`
  - Оценки: `num_assessments_submitted`, средний балл, `is_late`
  - Последовательные (понедельные) признаки (недели 0–39): `weekly_clicks`, `is_active`, `cumulative_clicks`, `click_trend`, `weeks_since_active`, `assessment_score`, `assessment_submitted`
  - Таргет: `is_at_risk` (доля withdrawal 31.2%, 32 593 регистрации)
- **Третий, ещё более простой набор признаков** — `app/components/data_loader.py::train_risk_model()`: `total_clicks`, `active_days`, `assessments_submitted`, `avg_score`, `min_score`, `num_of_prev_attempts`, `studied_credits`, `unregistered` + 3 label-encoded демо-колонки. Используется только живым приложением, модель переобучается заново на каждый cache-miss.

### 2.3 Обученные модели

| Модель | Файл / ноутбук | Библиотека | Статус | Сохранённый артефакт |
|---|---|---|---|---|
| Logistic Regression | `notebooks/03_baseline_executed.ipynb` (инлайн) | scikit-learn | обучена, оценена | только метрики (`results/metrics/logistic_regression_metrics.csv`), без `.pkl` |
| Random Forest | `03_baseline_executed.ipynb` + заново в `app/components/data_loader.py` | scikit-learn | обучена (дважды, разными признаками) | без сохранённого файла модели; app переобучает на лету |
| LSTM | `notebooks/04_lstm_executed.ipynb` | PyTorch (`nn.LSTM`, не `src.models.LSTMModel`) | обучена | **`results/lstm_best_model.pth`** (221 КБ) |
| "TFT" | `notebooks/05_tft_executed.ipynb` | PyTorch, кастомный класс `TemporalAttentionModel` | обучена | **`results/tft_best_model.pth`** (351 КБ) |
| XGBoost | — | — | **нигде не используется**, хотя есть в `requirements.txt` |
| N-BEATS | — | — | **кода нет нигде** (см. §3) |

**Важный нюанс:** то, что называется "TFT" в ноутбуке 05, **не является настоящим Temporal Fusion Transformer**. Сам заголовок ноутбука честно называет его "TFT-Inspired Model (Simplified Temporal Attention)": `Linear+ReLU → nn.LSTM → nn.MultiheadAttention (self-attn) → residual+LayerNorm → masked mean-pool → FFN head`, с каузальным маскированием для симуляции раннего предупреждения.

Отдельно в `src/models.py` есть класс `TFTModel` — обёртка вокруг **настоящего** `pytorch_forecasting.TemporalFusionTransformer`, но он **никогда не запускался** ни одним ноутбуком и не связан с приложением — чистый незадействованный скаффолд.

**Итоговые метрики** (`results/final_report.md`):

| Модель | AUC | F1 | Accuracy | Sensitivity |
|---|---|---|---|---|
| Logistic Regression | 0.9375 | 0.8596 | 0.8560 | 0.8900 |
| Random Forest (лучшая общая) | 0.9472 | 0.8629 | 0.8584 | 0.9489 |
| LSTM | 0.9436 | 0.8611 | 0.8564 | 0.9578 |
| TFT-Inspired | 0.9433 | 0.8619 | 0.8573 | 0.9519 |

Лучшая модель раннего предупреждения (temporal AUC на 5-й неделе): TFT-Inspired 0.759 против LSTM 0.429.

### 2.4 SHAP / объяснимость

Две отдельные, не переиспользуемые (ad-hoc) реализации:

- **`notebooks/06_shap_executed.ipynb`**: `shap.TreeExplainer(rf)` на Random Forest + `shap.KernelExplainer(tft_predict_static, X_bg)` на TFT-Inspired модели (т.к. она не древовидная). Топ-предикторы RF: `last_active_week`, `activity_span`, `num_assessments_submitted`, `mean_score`, `active_weeks`. RF и TFT расходятся в топ-3 факторах.
- **`app/components/data_loader.py::train_risk_model()`**: `shap.TreeExplainer(rf)` на app-специфичной RF, с защитным разбором разных форматов shap-выхода (`list` / `ndim==3`). Используется для `top_risk_reason` на странице и для `charts.py::shap_bar_chart()`.
- **Нет единой переиспользуемой SHAP-обёртки** — словарь русских подписей признаков (`feat_labels`/`feature_labels`) **скопирован 3 раза** в `data_loader.py`, `02_Analytics.py`, `03_AI_Advisor.py`.

### 2.5 Streamlit-страницы

- **`app/main.py`** — главный дашборд ("Стратегический дашборд"): health index (композит withdrawal rate / avg score / activity), rule-based алерты, 4 KPI-карточки, line-chart активности, donut-chart риска, гистограмма оценок, разбивка по `final_result`.
- **`app/pages/01_Students.py`** — "Студенты": топ-5 студентов, требующих внимания (с SHAP-причиной), фильтруемая/искомая таблица студентов, экспорт в CSV, сводка по уровням риска.
- **`app/pages/02_Analytics.py`** — "Аналитика": сравнение факультетов, рейтинговая таблица, захардкоженные бенчмарки (топ-100 мира, СНГ, Казахстан), **наивный линейный прогноз retention** (экстраполяция по последним 8 неделям, НЕ реальная модель), live-данные World Bank API с хардкод-фолбэком, SHAP bar-chart факторов.
- **`app/pages/03_AI_Advisor.py`** — "AI Советник": чат с LLM. Вызывает **Groq** (`llama-3.3-70b-versatile`) через `requests.post`, а **не** Anthropic SDK, несмотря на `anthropic` в `requirements.txt` и `ANTHROPIC_API_KEY` в `.env`.

### 2.6 Переиспользуемые utils/helpers (важно для нового модуля)

**`app/components/data_loader.py`** — паттерн, который реально используется в приложении:
- `load_raw_data()` — `@st.cache_data`, читает сырые CSV
- `get_faculty_data(module_code)` — `@st.cache_data`, фильтрация + мердж агрегатов
- `get_weekly_activity(module_code)` — понедельная агрегация
- `get_all_faculties_summary()` — health index по всем факультетам
- `train_risk_model(module_code)` — `@st.cache_data`, обучение RF + SHAP + risk score/level
- `compute_health_index(df)`, `get_alerts(df)` — бизнес-логика/алерты
- `get_retention_data(module_code)` — наивный линейный прогноз (не настоящая time-series модель)
- Константы: `FACULTY_MAP`, `RISK_COLORS`, `RISK_LABELS_RU`, `RESULT_RU`

**`app/components/charts.py`** — все графики через общий `_base(fig, title, height)` helper для единого стиля (прозрачный фон, общая палитра `C_VIOLET/C_INDIGO/C_BLUE/C_DARK/C_MUTED`).

**`app/components/styles.py`** — `GLASS_CSS` (общая CSS-тема) + `sidebar_logo(selected_code, faculty_map)` (сайдбар + селектор, хранит выбор в `st.session_state`).

**`src/` (чистая библиотека, НЕ используется пайплайном, но хороший референс по паттернам)**:
- `config.py` — централизованные `Path`-константы, `RANDOM_SEED=42`, `MODEL_PARAMS`
- `evaluate.py` — `compute_metrics`, `compute_temporal_auc`, `save_metrics`, `compare_models`
- `visualize.py` — `plot_temporal_auc`, `plot_feature_importance`, `plot_confusion_matrix`, `plot_roc_curve` (сохраняют `.png` + `.pdf`)

Нигде не используется `st.cache_resource` — только `st.cache_data` (в т.ч. для обучения модели, что нестандартно, но рабочее решение).

### 2.7 Версии ключевых библиотек

Из `requirements.txt` (с учётом незакоммиченной локальной правки):

```
pandas>=2.0.0, numpy>=1.24.0, scipy>=1.10.0
scikit-learn>=1.3.0, xgboost>=2.0.0          # xgboost нигде не используется
torch>=2.0.0, pytorch-lightning>=2.0.0
pytorch-forecasting>=1.0.0                    # используется только мёртвым src/models.py::TFTModel
shap>=0.43.0
matplotlib>=3.7.0, seaborn>=0.12.0, plotly>=5.15.0
jupyter>=1.0.0, ipykernel>=6.0.0, ipywidgets>=8.0.0
streamlit>=1.32.0
anthropic>=0.20.0                             # не используется — приложение зовёт Groq напрямую
requests>=2.31.0
tqdm>=4.65.0, pyyaml>=6.0, python-dotenv>=1.0.0
```

`prophet` — отсутствует. `pyproject.toml`/`Pipfile` — отсутствуют. `setup.py` существует отдельно (пакет `eduforecast`, `extras_require={"tft": [...]}`), не включает streamlit-зависимости.

### 2.8 TODO / заглушки / незавершённый код

- Поиск `TODO|FIXME|XXX|not implemented|NotImplementedError` по `src/` и `app/` — **0 совпадений**.
- Единственный `pass` — `app/pages/01_Students.py:113`, намеренный (`except ValueError: pass` при парсинге ID поиска).
- Структурная, не помеченная незавершённость: `src/models.py::TFTModel` (настоящий TFT-враппер) полностью написан, но никогда не запускался/не протестирован на данных — мёртвый, непроверенный код. Аналогично весь `src/features.py`, `evaluate.py`, `visualize.py` — рабочий, но не задействован реальным пайплайном.

---

## 3. Модуль Enrollment/Course Load (N-BEATS) — явный статус

Проведён исчерпывающий поиск по всему репозиторию (код, ноутбуки, markdown, история коммитов):

```
grep -rni "n-beats|nbeats" .            → 0 совпадений
grep -rni "enrollment|course load" .    → 0 совпадений
git log --all --grep "enrollment|nbeats" → 0 совпадений
```

**Однозначный вывод: модуля "Enrollment/Course Load (N-BEATS)" в репозитории нет вообще — ни в коде, ни в документации, ни в истории коммитов, ни единым упоминанием.** Это не "задокументировано, но не реализовано" — это полное отсутствие в любом артефакте текущего репо. Если модуль упоминается в тексте диссертации/статье — этот текст не входит в кодовую базу. Строить придётся с нуля, без единой заготовки.

(Для сравнения: "TFT" в ноутбуке 05 — это реальный, хоть и упрощённый, код; он не имеет отношения к N-BEATS.)

---

## 4. Предлагаемая архитектура нового модуля "Research" (научная продуктивность)

**Это план, код не пишется — на подтверждение.**

### 4.1 Структура папок/файлов (по аналогии с Academic)

Исходя из аудита: реальный рабочий паттерн приложения — это `app/components/*`, а не неиспользуемый `src/`. Поэтому новый модуль лучше строить по образцу `app/components/`, а не дублировать судьбу `src/`.

```
data/
  research/
    raw/                      # кэш сырых ответов OpenAlex API (JSON/parquet), по вузу
    processed/                # агрегаты по годам/подразделениям

notebooks/
  07_research_eda.ipynb         # разведка: объём данных по вузу, покрытие по годам
  08_research_features.ipynb    # агрегация публикаций/цитирований
  09_research_forecast.ipynb    # time-series модель, сравнение подходов

src/research/                   # по образцу src/, но с намерением реально подключить к app/
  __init__.py
  openalex_client.py            # обёртка над OpenAlex API: пагинация, rate-limit, кэш на диск
  aggregate.py                  # агрегация works → по годам/подразделениям
  forecast.py                   # обёртка Prophet (и опционально N-BEATS) с единым интерфейсом fit()/predict()

app/
  components/
    research_data_loader.py     # @st.cache_data загрузчики, по образцу app/components/data_loader.py
    research_charts.py          # Plotly-графики через существующий charts.py::_base()
  pages/
    04_Research.py              # новая страница "Научная продуктивность"

results/
  research/
    figures/, metrics/           # по аналогии с существующей results/
```

### 4.2 Что переиспользовать из Academic напрямую

- **`app/components/charts.py::_base()`** и цветовая палитра (`C_VIOLET`/`C_INDIGO`/...) — взять как есть, чтобы графики нового модуля визуально не отличались от существующих.
- **`app/components/styles.py::GLASS_CSS`, `sidebar_logo()`** — переиспользовать напрямую; возможно, расширить сайдбар выбором модуля (Academic / Research), а не только факультета.
- **Паттерн кэширования** `@st.cache_data(show_spinner="...")` из `data_loader.py` — повторить один в один для загрузчиков OpenAlex-данных (кэш особенно важен, т.к. API-вызовы медленнее, чем чтение локальных CSV).
- **SHAP-обёртка** — только если в Research-модуле появится модель с табличными признаками (например, предсказание "попадёт ли публикация в топ по цитируемости" по признакам подразделения/области). Для чистого time-series прогноза (Prophet/N-BEATS) SHAP не применим напрямую — это не нужно тянуть сейчас.
- **НЕ копировать** паттерн "3 независимые реализации одной логики" (`src/` vs ноутбуки vs `app/`), который сложился в Academic-модуле — в новом модуле стоит сразу писать код один раз в `src/research/` и импортировать его и из ноутбуков, и из `app/components/`.

### 4.3 Минимальный pipeline

1. **Сбор данных** — OpenAlex API, `GET https://api.openalex.org/works?filter=institutions.id:<OpenAlex ID вуза>&per-page=200&cursor=...`, пагинация курсором, обязательно `mailto=` в запросах (polite pool — выше rate limit, без ключа). Извлекать: `publication_year`, `cited_by_count`, `concepts` (поле/область), `authorships[].institutions`, `authorships[].raw_affiliation_strings` (для возможной разбивки по подразделениям — см. риски).
2. **Агрегация** — группировка по году (и, если данные позволяют, по укрупнённой области/подразделению) → число публикаций в год, сумма/медиана цитирований, кумулятивные цитирования, возможно рост по областям (concepts).
3. **Time-series модель** — **рекомендация: начать с Prophet, не с N-BEATS.** Обоснование:
   - Ожидаемый объём данных — это **годовой ряд по одному вузу**, скорее всего 10–20 точек (лет). N-BEATS — generic DL-архитектура, которая эффективна при наличии многих параллельных рядов или длинных последовательностей; на 10–20 точках она, скорее всего, переобучится или не превзойдёт тривиальный тренд.
   - Prophet спроектирован именно для коротких, разреженных, годовых/сезонных рядов с небольшим числом точек, даёт доверительные интервалы из коробки и проще защищается в тексте диссертации (интерпретируемая декомпозиция тренд+сезонность).
   - N-BEATS можно добавить **вторым, сравнительным** вариантом позже, если агрегация по подразделениям/областям даст достаточно параллельных рядов (global N-BEATS неплохо работает на множестве коротких рядов одновременно) — но это решение принимать после проверки объёма данных (см. §4.4), а не до.
4. **Визуализация** — новая страница `04_Research.py`: линия факт+прогноз публикаций/цитирований в год с доверительным интервалом (аналог `retention_forecast_chart`, но с реальной моделью вместо линейной экстраполяции), разбивка по областям/подразделениям (если данных хватит), опционально — сравнение с вузами-аналогами через тот же OpenAlex API.

### 4.4 Риски — и как проверить ДО начала реализации

**Главный риск: по конкретному вузу (AIU) в OpenAlex может оказаться слишком мало публикаций для содержательного прогнозирования.** Это нужно проверить **до** написания пайплайна, а не после:

1. Найти OpenAlex institution ID для AIU: `GET https://api.openalex.org/institutions?search=Astana IT University` (или `Astana IT University` под другим написанием/ROR ID) — свериться, что находится правильная организация, а не похожая по названию.
2. Одним запросом получить агрегат по годам: `GET https://api.openalex.org/works?filter=institutions.id:<ID>&group_by=publication_year` — это даёт число публикаций по годам **без скачивания всех works**, самый дешёвый способ оценить объём.
3. Критерии "стоп/продолжать":
   - Если **суммарно < ~50 публикаций** за всю историю индексации — содержательный time-series прогноз по годам почти наверняка не будет статистически устойчив; вместо полноценного forecasting-пайплайна лучше ограничиться дескриптивной аналитикой (тренд, рост по годам, топ-области) без ML-модели, либо расширить агрегацию (например, на уровень Казахстана/региона, а не одного вуза).
   - Если **ряд короче ~8 лет** или имеет большие провалы (годы без данных) — тоже сигнал пересмотреть масштаб анализа (например, квартальная агрегация вместо годовой, если у OpenAlex для этого вуза вообще набегает достаточно публикаций).
4. **Дополнительный риск — разрешение аффилиации (institution disambiguation).** Название вуза в OpenAlex может быть неточным/неполным, особенно для относительно нового или не-англоязычного вуза — есть риск как ложноположительных (смешение с похожими названиями), так и ложноотрицательных (часть публикаций указана с другим написанием названия и не попадёт под фильтр `institutions.id`) совпадений. Перед агрегацией стоит вручную просмотреть выборку из 20–30 найденных works и проверить, что все они реально относятся к нужному вузу.
5. **Риск гранулярности по подразделениям** — у OpenAlex обычно нет чистого институционального ID на уровне факультета/кафедры; разбивка по подразделениям потребует парсинга текстовых `raw_affiliation_strings` (шумных, на разных языках) — это нетривиальная NLP-задача сама по себе. Если бюджет времени ограничен, на первой итерации стоит агрегировать весь вуз целиком, без разбивки по подразделениям, и добавить её только если пп. 1–2 покажут достаточный объём данных.
6. **Rate limits / инфраструктура** — у OpenAlex нет обязательной авторизации, но вежливый пул (через `mailto=`) ограничен; для воспроизводимости и скорости работы Streamlit-страницы нужен локальный кэш сырых ответов (`data/research/raw/`), а не live-запрос при каждом открытии страницы.

**Рекомендация по порядку действий:** сначала выполнить шаги 1–2 (один-два API-запроса, без какого-либо кода пайплайна) и показать мне фактические цифры по годам для AIU — после этого подтверждать, строить ли полноценный Prophet/N-BEATS pipeline или ограничиться более простой аналитикой.

---

*Код для модуля Research не писался — ждёт подтверждения плана.*
