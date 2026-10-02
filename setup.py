from setuptools import find_packages, setup

setup(
    name="eduforecast",
    version="0.1.0",
    description=(
        "EduForecast: Unified AI Early Warning and Decision Support System "
        "for Higher Education"
    ),
    author="",
    python_requires=">=3.10",
    packages=find_packages(),
    install_requires=[
        "pandas>=2.0.0",
        "numpy>=1.24.0",
        "scipy>=1.10.0",
        "scikit-learn>=1.3.0",
        "xgboost>=2.0.0",
        "torch>=2.0.0",
        "pytorch-lightning>=2.0.0",
        "shap>=0.43.0",
        "matplotlib>=3.7.0",
        "seaborn>=0.12.0",
        "plotly>=5.15.0",
        "tqdm>=4.65.0",
        "pyyaml>=6.0",
        "python-dotenv>=1.0.0",
    ],
    extras_require={
        "tft": ["pytorch-forecasting>=1.0.0"],
    },
)
