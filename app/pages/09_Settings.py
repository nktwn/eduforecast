import sys
from importlib import metadata
from pathlib import Path

for _p in (Path(__file__).resolve().parents[1], Path(__file__).resolve().parents[2]):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from components import theme, ui  # noqa: E402
from components.shell import DATA_CHECKS, key_status_cached  # noqa: E402
from src.advisor.config import LOG_PATH, load_settings  # noqa: E402
from src.advisor.facts.registry import SNAPSHOT_PATH, registry  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = ROOT / "data" / "app_cache"
LIBS = ["streamlit", "pandas", "numpy", "scikit-learn", "lightgbm", "shap", "prophet", "plotly", "requests"]

ui.page_header("Настройки и состояние", "Ключ и модель советника, данные, версии, реестр фактов. Ключ здесь не "
                                        "показывается и не вводится: только в .env или .streamlit/secrets.toml.")
s = load_settings()
status = key_status_cached(s.base_url, s.model, s.has_key)
c1, c2, c3 = st.columns(3)
with c1:
    ui.kpi_card("Ключ LLM", status, hint="нет / есть / недействителен / не проверен (нет сети)")
with c2:
    ui.kpi_card("Модель", s.model, hint=f"провайдер: {s.provider_name}; таймаут {theme.num(s.timeout)} с")
with c3:
    reg = registry()
    ui.kpi_card("Реестр фактов", theme.num(len(reg.facts)), hint=f"собран {theme.ru_date(reg.built_at, True)}")

st.markdown('<div class="section-title">Переменные окружения</div>', unsafe_allow_html=True)
st.markdown("""
| переменная | назначение | по умолчанию |
|---|---|---|
| `GROQ_API_KEY` или `ADVISOR_API_KEY` | ключ LLM-провайдера | — (без ключа работает брифинг) |
| `ADVISOR_MODEL` | модель | `openai/gpt-oss-120b` |
| `ADVISOR_BASE_URL` | OpenAI-совместимый endpoint | `https://api.groq.com/openai/v1` |
| `ADVISOR_TIMEOUT` | таймаут запроса, с | `30` |
""")

st.markdown('<div class="section-title">Данные</div>', unsafe_allow_html=True)
rows = [{"Набор": name, "Файл": str(p.relative_to(ROOT)), "Есть": "да" if p.exists() else "нет"}
        for name, p in DATA_CHECKS.items()]
rows.append({"Набор": "Предрасчёт для быстрых страниц", "Файл": str(CACHE_DIR.relative_to(ROOT)),
             "Есть": "да" if (CACHE_DIR / "meta.json").exists() else "нет (python scripts/prepare_app.py)"})
st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

st.markdown('<div class="section-title">Версии</div>', unsafe_allow_html=True)
vers = []
for lib in LIBS:
    try:
        vers.append({"Библиотека": lib, "Версия": metadata.version(lib)})
    except metadata.PackageNotFoundError:
        vers.append({"Библиотека": lib, "Версия": "не установлена"})
st.dataframe(pd.DataFrame(vers), hide_index=True, width="stretch")
st.caption(f"Python {sys.version.split()[0]}. Закреплённые версии — requirements.txt.")

st.markdown('<div class="section-title">Служебное</div>', unsafe_allow_html=True)
st.markdown(f"- Снимок реестра: `{SNAPSHOT_PATH.relative_to(ROOT)}`; пересборка: `python -m src.advisor.facts.registry`\n"
            f"- Журнал запросов советника: `{LOG_PATH.relative_to(ROOT)}` (в .gitignore, без персональных данных)")
