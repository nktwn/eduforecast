# DevOps: Docker, Jenkins CI/CD, test deployment

This folder documents the CI/CD setup of EduForecast-SIS (Assignment 5).
Operations: [RUNBOOK.md](RUNBOOK.md). Measured results: [EVIDENCE.md](EVIDENCE.md).
Screenshot list: [screenshots/README.md](screenshots/README.md). Console logs: [ci-logs/](ci-logs/).
Facts for the written report: [REPORT_FACTS.md](REPORT_FACTS.md).

## Quick start (from a fresh clone)

Prerequisites: Docker Desktop with at least 4 GB of VM memory and about 8 GB of free disk, GNU make,
free ports 8080, 8502 and 5000 on 127.0.0.1. Tested on macOS arm64 (Docker Desktop 4.37, engine 27.4).

```bash
git clone https://github.com/nktwn/eduforecast.git && cd eduforecast
make jenkins-env      # jenkins/.env.jenkins (git-ignored): random admin password,
                      # GIT_REPO_URL=https://github.com/nktwn/eduforecast.git
make jenkins-up       # builds the controller image (~9 min the first time), starts http://localhost:8080
make registry-up      # optional: local registry 127.0.0.1:5000 for the PUSH_IMAGE parameter
```

1. Open http://localhost:8080, log in as `admin` with `JENKINS_ADMIN_PASSWORD` from `jenkins/.env.jenkins`.
2. The job `eduforecast` exists already (Job DSL). Within 2 minutes it scans GitHub and builds `main`
   (or click **Scan Multibranch Pipeline Now** once).
3. A green `main` build deploys the app to http://localhost:8502 (`curl -s http://localhost:8502/_stcore/health` → `ok`).
4. Push to a registry: branch → **Build with Parameters** → `PUSH_IMAGE=true`, `REGISTRY_IMAGE=localhost:5000/eduforecast`.
5. Check everything at once: `scripts/devops/final_check.sh` (read-only, PASS/FAIL per item).

Without Jenkins: `make docker-test` (tests in the container), `make docker-build`, `make docker-run`
(app on http://localhost:8501). Stop: `make jenkins-down`, `make registry-down`,
`docker rm -f eduforecast-test`. All commands: [RUNBOOK.md](RUNBOOK.md).

## Architecture

```mermaid
flowchart LR
    dev[Developer commit] --> gh[GitHub nktwn/eduforecast]
    dev -. pre-push validation .-> mirror[Local bare mirror<br/>~/.eduforecast-ci/eduforecast.git]
    gh -- periodic branch scan, 2 min --> jenkins
    mirror -. pre-publication validation only .-> jenkins
    subgraph host[Docker Desktop on macOS arm64]
        jenkins[Jenkins LTS 2.580.2 JDK 21<br/>eduforecast-jenkins, 127.0.0.1:8080<br/>JCasC + Job DSL]
        jenkins -- docker.sock --> daemon[(Docker daemon)]
        daemon --> testimg[Test image<br/>ruff + pytest 123/7]
        testimg --> runtime[Runtime image<br/>eduforecast:SHA, non-root]
        runtime --> smoke[Smoke container<br/>ef-smoke-*: health, 12 pages]
        smoke --> reg[(Registry<br/>localhost:5000 or Docker Hub)]
        smoke --> testsrv[Test server<br/>eduforecast-test, 127.0.0.1:8502]
        runtime -. optional, not executed .-> k3d[k3d cluster eduforecast]
    end
```

## Components

| file | purpose |
|---|---|
| `Dockerfile` | multi-stage: `base` (python:3.12.13-slim-bookworm + `requirements-ci.txt` + libgomp1), `test` (+ git, ruff 0.16.10, pytest-cov 7.1.0, full tree), `runtime` (default; non-root uid 10001, only runtime files, OCI labels, HEALTHCHECK on `/_stcore/health`) |
| `.dockerignore` | allowlist: build context is about 1.2 MB, no `.git`, `.venv`, `.env*`, datasets or caches |
| `scripts/devops/page_smoke.py` | renders every page listed in `app/main.py` with Streamlit AppTest; fails on any exception |
| `scripts/devops/smoke_container.sh` | runs the runtime image on a private network, waits for `healthy`, checks health from a second container, non-root, no `.env`, runs `page_smoke.py` |
| `jenkins/` | controller image (Docker CLI + buildx, pinned plugins), `docker-compose.yml`, JCasC (`casc/jenkins.yaml`), optional Docker Hub credential, `.env.jenkins.example` |
| `Jenkinsfile` | Checkout, Build test image, Lint, Unit tests (JUnit + coverage), Build image, Smoke test, Push image (optional), Deploy to test server (main) |
| `scripts/devops/sync_mirror.sh` | updates the local bare mirror Jenkins reads before anything is pushed to GitHub |
| `k8s/`, `scripts/devops/k3d_*.sh`, `k8s_deploy.sh` | optional Kubernetes (k3d) deployment; written but not executed (owner declined installing k3d) |
| `scripts/devops/prepush_audit.sh` | secret and data scan of what would be pushed |
| `Makefile` | shortcuts: `docker-build`, `docker-test`, `jenkins-up`, `smoke`, `mirror-sync`, ... |

## Pipeline

| stage | what it does | fails when |
|---|---|---|
| Checkout | prints branch, commit, short SHA, Docker versions | — |
| Build test image | `docker build --target test` | dependency or build error |
| Lint | `ruff check --select E9,F63,F7,F82 app src tests` (same as `.github/workflows/ci.yml`) | syntax errors / undefined names |
| Unit tests | `docker run` of the test image, `docker cp` of `junit.xml` and `coverage.xml`, JUnit report, artifacts | any failing test (exit code of pytest) |
| Build image | runtime target, tags `<sha>`, `build-<N>`, `latest` (main only); archives `image-info.txt`, `pip-freeze.txt` | build error |
| Smoke test | `scripts/devops/smoke_container.sh` | not healthy in 60 s, root user, `.env` found, page exception |
| Push image | only with `PUSH_IMAGE=true`; `localhost:*` registries without login, others via the `dockerhub-credentials` credential and `docker login --password-stdin` in a temporary `DOCKER_CONFIG` | registry/credential error |
| Deploy to test server | `DEPLOY_TEST=true` and branch `main`: replaces container `eduforecast-test` on `127.0.0.1:8502`, waits for healthy, checks health from a second container | not healthy in 90 s |

`post { always }` removes only this build's `ef-tests-*`, `ef-smoke-*` resources and the build's test-image tag, then cleans the workspace.

### How "tests on every commit" works

One trigger only: the multibranch job (`jenkins/casc/jenkins.yaml`, `periodicFolderTrigger 2m`) scans
`https://github.com/nktwn/eduforecast.git` every 2 minutes. When a branch head has moved, branch
indexing starts exactly one build of that commit (cause `Branch indexing`); a new branch gets its
first build the same way. Expected delay from `git push` to build start: up to about 2 minutes.

- The Jenkinsfile has no `triggers {}` block. An earlier version also had `pollSCM('H/2 * * * *')`;
  both mechanisms saw the same commit and built it twice (mirror run main #3, see EVIDENCE.md).
- No GitHub webhook: Jenkins listens on 127.0.0.1 only, so github.com cannot reach it. A webhook
  would need a public URL or a tunnel, which this local study setup avoids on purpose.

## Design decisions

- **No data, no secrets in images.** The app runs in "no data" / briefing mode; pages without data show empty states (verified by `page_smoke.py`). `.env` never enters the build context.
- **Runtime files were traced, not guessed.** An audit hook recorded every file the pages open: `.streamlit/config.toml`, `data/aitu/financials_2019_2020.csv`, `data/research/raw/yearly_work_counts_I4405257690.json`, `src/advisor/facts/snapshot.json`, `src/finance/rules.yaml`.
- **Writable directories for the non-root user.** `src/research/config.py` and `src/finance/config.py` create directories at import time and the advisor writes `logs/`, so `data/`, `results/`, `logs/`, `docs/` in the image belong to the app user; the code stays root-owned.
- **Jenkins as root with the Docker socket** is root-equivalent on the Docker host. Acceptable only for this local study setup: Jenkins listens on 127.0.0.1 only and has no agent port.
- **Tests run in containers, not in the Jenkins JVM container**, so the Jenkins image needs no Python.
