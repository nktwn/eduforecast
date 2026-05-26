# EduForecast

**Unified AI Early Warning and Decision Support System for Higher Education**

EduForecast predicts student dropout risk from weekly VLE interaction data
using the Open University Learning Analytics Dataset (OULAD).
Three models are compared — Random Forest, LSTM, and Temporal Fusion
Transformer — and predictions are explained with SHAP.

---

## Installation

```bash
git clone <your-repo-url>
cd eduforecast
pip install -r requirements.txt
```

For TFT support (optional, may require manual dependency resolution):

```bash
pip install pytorch-forecasting>=1.0.0
# If the above fails:
pip install pytorch-forecasting --no-deps
pip install lightning einops
```

---

## Quick Start

1. **Download OULAD** — follow the instructions in [data/README.md](data/README.md).
2. **Run notebooks in order:**

| Notebook | Purpose |
|----------|---------|
| `01_eda.ipynb` | Exploratory data analysis |
| `02_features.ipynb` | Feature engineering |
| `03_baseline.ipynb` | Logistic Regression & Random Forest |
| `04_lstm.ipynb` | LSTM model |
| `05_tft.ipynb` | Temporal Fusion Transformer |
| `06_shap.ipynb` | SHAP explainability |

---

## Project Structure

```
eduforecast/
├── data/
│   ├── raw/          ← OULAD CSV files (not tracked in git)
│   └── processed/    ← engineered features (not tracked in git)
├── notebooks/        ← analysis notebooks (run in order 01→06)
├── src/
│   ├── config.py     ← paths and hyperparameters
│   ├── data_loader.py
│   ├── features.py
│   ├── models.py
│   ├── evaluate.py
│   └── visualize.py
└── results/
    ├── figures/
    ├── metrics/
    └── final_report.md
```

---

## Models

| Model | Library | Purpose |
|-------|---------|---------|
| Random Forest | scikit-learn | Tabular baseline |
| LSTM | PyTorch | Sequential / temporal |
| TFT | pytorch-forecasting | Multi-horizon temporal with attention |

---

## Dataset

> Kuzilek, J., Hlosta, M., & Zdrahal, Z. (2017).
> *Open University Learning Analytics dataset.*
> Scientific Data, 4, 170171.
> <https://doi.org/10.1038/sdata.2017.171>
