# syntax=docker/dockerfile:1.7
#
# EduForecast-SIS container image.
#   base    - Python + pinned app/test dependencies (requirements-ci.txt)
#   test    - base + lint/coverage tools + the full source tree; runs ruff and pytest
#   runtime - base + only what the Streamlit app reads at runtime; non-root (default target)
#
# No datasets (OULAD, IPEDS, caches) and no secrets are copied: the app runs in
# "no data" / briefing mode. See docs/devops/README.md.

ARG PYTHON_IMAGE=python:3.12.13-slim-bookworm

FROM ${PYTHON_IMAGE} AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    MPLCONFIGDIR=/tmp/mpl \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    PYTHONPATH=/app

# libgomp1: OpenMP runtime needed by the lightgbm wheel on Debian.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements-ci.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements-ci.txt


FROM base AS test

# git: tests/test_advisor_facts.py calls `git ls-files`. The context has no .git, so the
# command returns an empty list there and that test skips, as in a checkout without results.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# pytest itself is pinned in requirements-ci.txt; ruff matches the owner's venv.
ARG RUFF_VERSION=0.16.10
ARG PYTEST_COV_VERSION=7.1.0
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install "ruff==${RUFF_VERSION}" "pytest-cov==${PYTEST_COV_VERSION}"

COPY . .

CMD ["sh", "-c", "mkdir -p /tmp/reports && pytest -q -p no:cacheprovider --junitxml=/tmp/reports/junit.xml --cov=app --cov=src --cov-report=xml:/tmp/reports/coverage.xml --cov-report=term"]


FROM base AS runtime

ARG GIT_SHA=unknown
ARG BUILD_DATE=unknown
ARG SOURCE_URL=https://github.com/nktwn/eduforecast
LABEL org.opencontainers.image.title="eduforecast" \
      org.opencontainers.image.description="EduForecast-SIS Streamlit app (no data, briefing mode)" \
      org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.source="${SOURCE_URL}"

RUN useradd --uid 10001 --create-home --home-dir /home/app --shell /usr/sbin/nologin app

# Code and the tracked files the pages read at runtime (traced with an audit hook).
COPY app/ app/
COPY src/ src/
COPY .streamlit/config.toml .streamlit/config.toml
COPY data/aitu/ data/aitu/
COPY data/research/raw/yearly_work_counts_I4405257690.json data/research/raw/
COPY scripts/devops/page_smoke.py scripts/devops/page_smoke.py

# The code is read-only for the app user; these directories are created at import
# time (src/research/config.py, src/finance/config.py) or written at runtime
# (logs/advisor_queries.jsonl, data/app_cache/), so the app user owns them.
RUN mkdir -p data/research data/finance data/app_cache results logs docs/finance_audit \
    && chown -R app:app data results logs docs

USER app
ENV HOME=/home/app

EXPOSE 8501

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=4).read() == b'ok' else 1)"

CMD ["streamlit", "run", "app/main.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
