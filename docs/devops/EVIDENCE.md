# Evidence

All numbers below come from command output or the Jenkins API on 2026-10-30 (host: MacBook Apple M2,
arm64, 8 GB RAM; Docker Desktop 27.4.0, VM memory 3.83 GiB). Full console logs: [ci-logs/](ci-logs/).
Jenkins runs read the local mirror `file:///mirror/eduforecast.git` (nothing was pushed to GitHub);
the mirror's `main` = branch `devops/docker-jenkins`.

## Pipeline runs

Times are local (UTC+5). Tests: passed / failed / skipped from the Jenkins JUnit report.
Image size: `docker image inspect .Size` (Docker Desktop containerd store; `docker images` lists the same image as 1.64 GB of disk).

| branch #build | commit | trigger | result | duration | tests | image size | tags | notes |
|---|---|---|---|---|---|---|---|---|
| main #1 | 5e1d040 | Branch indexing (19:34:18; mirror updated 19:32:34) | SUCCESS | 63.4 s | 123 / 0 / 7 | 357,629,334 B | 5e1d0408, build-1, latest | first deploy: `none -> eduforecast:5e1d0408` |
| main #2 | 39a3c2e | **Started by an SCM change** (pollSCM), 38 s after the commit reached the mirror | SUCCESS | 84.7 s | 123 / 0 / 7 | 357,629,375 B | 39a3c2e4, build-2, latest | deploy replaced the container: `eduforecast:5e1d0408 -> eduforecast:39a3c2e4` |
| main #3 | 39a3c2e | Branch indexing | SUCCESS | 47.7 s | 123 / 0 / 7 | 357,629,385 B | 39a3c2e4, build-3, latest | duplicate of #2 (see difficulties) |
| main #4 | 39a3c2e | Started by user admin, `PUSH_IMAGE=true`, `REGISTRY_IMAGE=localhost:5000/eduforecast` | SUCCESS | 51.9 s | 123 / 0 / 7 | 357,629,372 B | 39a3c2e4, build-4, latest | pushed to local registry (Push image 7.2 s) |
| main #5 | 366fdf8 | Branch indexing, 76 s after the commit reached the mirror | SUCCESS | 58.5 s | 123 / 0 / 7 | 357,629,393 B | 366fdf8c, build-5, latest | deploy `eduforecast:39a3c2e4 -> eduforecast:366fdf8c` |
| ci-failure-demo #1 | 0a67aa5 | Branch indexing | FAILURE | 1.7 s | — | — | — | checkout failed: mirror objects hard-linked (see difficulties) |
| ci-failure-demo #2 | 0a67aa5 | Started by user admin (re-run after the fix of the mirror) | **FAILURE at Unit tests** | 24.9 s | 122 / **1** / 7 | not built | — | `test_russian_format` broken on purpose; Build image, Smoke, Push, Deploy skipped |
| ci-failure-demo #3 | b1f8ac1 (revert) | Branch indexing, 17 s after the fix reached the mirror | SUCCESS | 48.0 s | 123 / 0 / 7 | 357,629,362 B | b1f8ac1d, build-3 | not main: no deploy; its `build-3` overwrote main #3's tag (fixed, see difficulties) |
| ci-failure-demo #4 | 366fdf8 | Branch indexing (mirror branch moved to the current head to verify branch-prefixed tags) | SUCCESS | 39.5 s | 123 / 0 / 7 | — | 366fdf8c, ci-failure-demo-build-4 | tag fix verified |

The negative-test commits exist only in the mirror branch `ci-failure-demo`; they were made in a throw-away
clone of the mirror and never touched the repository's branches or `origin`.

### Stage durations

| stage | main #1 | main #2 | main #4 (push) | ci-failure-demo #2 (red) |
|---|---|---|---|---|
| Checkout | 1.4 s | 1.3 s | 0.9 s | 1.2 s |
| Build test image | 8.8 s | 6.4 s | 1.8 s | 3.9 s |
| Lint | 1.0 s | 1.0 s | 0.6 s | 0.9 s |
| Unit tests | 22.0 s | 47.6 s | 15.8 s | 17.1 s (failed) |
| Build image | 3.5 s | 9.3 s | 4.1 s | skipped |
| Smoke test | 11.5 s | 9.6 s | 9.2 s | skipped |
| Push image | skipped | skipped | 7.2 s | skipped |
| Deploy to test server | 8.9 s | 6.6 s | 8.2 s | skipped |

### Registry check after main #4

```
$ curl -s http://127.0.0.1:5000/v2/_catalog
{"repositories":["eduforecast"]}
$ curl -s http://127.0.0.1:5000/v2/eduforecast/tags/list
{"name":"eduforecast","tags":["build-4","latest","39a3c2e4"]}
```

### Test server

```
$ docker ps --filter name=eduforecast-test --format '{{.Names}} {{.Image}} {{.Status}} {{.Ports}}'
eduforecast-test eduforecast:5e1d0408 Up 5 minutes (healthy) 127.0.0.1:8502->8501/tcp     # after main #1
eduforecast-test eduforecast:39a3c2e4 Up 9 seconds (healthy)                               # after main #2
$ curl -s http://localhost:8502/_stcore/health
ok
```

## Docker image (Phase 1, built by hand before Jenkins)

| check | result |
|---|---|
| `docker build --target test` (cold, empty pip cache) | 175 s, exit 0; no package compiled from source on linux/arm64 |
| test target rebuild after adding `git` (base layers cached) | 30 s |
| `docker build` runtime target (base cached) | 3 s; cached rebuild 2 s (5 steps `CACHED`) |
| build context | `transferring context: 1.19MB` |
| image sizes (`docker images`) | runtime `eduforecast:dev` 1.64 GB, test 1.81 GB; site-packages 1.1 GB (llvmlite 168M, pyarrow 139M, scipy 118M, pandas 74M, plotly 67M), app code 1.4 MB |
| architecture / user | `arm64`, `User=app` (uid 10001) |
| `docker history` | only `GIT_SHA`, `BUILD_DATE`, `SOURCE_URL` build args; no secrets |
| lint in test image | `ruff 0.16.10`: All checks passed! |
| pytest in test image | 123 passed, 7 skipped (same as a clean clone); coverage 43 % (`--cov=app --cov=src`) |
| imports + Prophet in runtime | `import streamlit, pandas, sklearn, lightgbm, prophet, shap` OK; `Prophet().fit()` on 30 points OK |
| container smoke (`smoke_container.sh`) | healthy, health `ok` from a second container, uid 10001, no `.env`/`secrets.toml`, 12/12 pages without exceptions ([log](ci-logs/smoke-local.txt)) |

The 7 skipped tests need local datasets (Finance panel, stage-2 result files) that are not in git and not in the image.

## Jenkins (Phase 2)

| check | result |
|---|---|
| image build `jenkins/jenkins:2.580.2-lts-jdk21` + Docker CLI + plugins | 520 s first build; 1.08 GB |
| start to healthy | 16 s (after the JCasC fix) |
| anonymous `GET /api/json` | HTTP 403 |
| wrong password | HTTP 401 |
| admin (password from `jenkins/.env.jenkins`, not printed) | HTTP 200, header `X-Jenkins: 2.580.2` |
| job | `eduforecast` (`WorkflowMultiBranchProject`), source `file:///mirror/eduforecast.git`, scan interval 120000 ms, script path `Jenkinsfile` |
| Jenkinsfile linter (`/pipeline-model-converter/validate`) | `Jenkinsfile successfully validated.` |
| `docker exec eduforecast-jenkins docker version` | client 29.9.2 / server 27.4.0 (linux/arm64); buildx v0.38.1 |
| Java in controller | OpenJDK 21.0.13 |
| plugins | [jenkins/plugins-resolved.txt](../../jenkins/plugins-resolved.txt) (15 top-level, pinned in `plugins.txt`) |

## Difficulties and fixes

| # | problem (exact error) | fix |
|---|---|---|
| 1 | `tests/test_advisor_facts.py` failed in the test image: `FileNotFoundError: [Errno 2] No such file or directory: 'git'` (1 failed, 123 passed, 6 skipped) | install `git` in the `test` stage only. Without `.git` in the context `git ls-files` returns nothing and the test skips, exactly as in a checkout without result files. No test code changed |
| 2 | Jenkins did not start: `UnknownAttributesException: ... DefaultCrumbIssuer : excludeClientIPFromCrumb` | removed the `crumbIssuer` block (default CSRF protection stays on); moved `COPY casc/` after the plugin layer so config edits do not re-download plugins |
| 3 | ci-failure-demo #1: `remote: error: unable to open loose object 8f9be2a... Permission denied` | the throw-away clone was made with `git clone <path>`, which hard-links objects into the mirror; Docker Desktop's file sharing could not read them. Re-cloned with `git clone --no-local` (0 hard links) and re-ran the build |
| 4 | `POST /job/.../build` → HTTP 400 | parameterized job: use `/buildWithParameters` |
| 5 | main #3 built the same commit as #2 | `pollSCM` (Jenkinsfile) started #2; 84 s later (19:41:09 → 19:42:33) the periodic branch scan saw the new head and started #3. Both triggers were requested. Fixed before publication: `pollSCM` removed from the Jenkinsfile; the 2-minute branch scan is the only trigger (see README "How tests on every commit works") |
| 6 | risk found before the first run (not a failure): `src/finance/config.py` and `src/research/config.py` create directories at import | `data/`, `results/`, `logs/`, `docs/` in the image are owned by the app user; code stays root-owned |
| 7 | `build-N` tags collided between branches: ci-failure-demo #3 re-tagged `eduforecast:build-3` that main #3 had created | non-main branches now get `<branch>-build-N` (commit 366fdf8); verified by ci-failure-demo #4 → `eduforecast:ci-failure-demo-build-4` |
| 8 | free disk on the host fell from 19 GiB to 9.2 GiB during the work (Docker Desktop disk image grew: Jenkins image, runtime/test images, build cache) | stale `eduforecast:*` tags removed; no further builds were needed. Docker.raw does not shrink automatically |

## Versions

| component | version |
|---|---|
| base image | `python:3.12.13-slim-bookworm` (linux/arm64) |
| Python deps | `requirements-ci.txt` (streamlit 1.57.0, pandas 3.0.3, scikit-learn 1.8.0, lightgbm 4.7.0, prophet 1.4.0, shap 0.51.0, pytest 9.1.1) |
| test tools | ruff 0.16.10, pytest-cov 7.1.0 (coverage 7.17.0) |
| Jenkins | `jenkins/jenkins:2.580.2-lts-jdk21`, OpenJDK 21.0.13 |
| Docker in Jenkins | docker-ce-cli 29.9.2, buildx v0.38.1 |
| registry | `registry:2.8.3` |
| host Docker | Docker Desktop, engine 27.4.0, compose v2.31.0 |

## Resource usage

| | start | end |
|---|---|---|
| free disk (`df -h .`) | 19 GiB | 9.2 GiB |
| `docker system df` images | 2.788 GB (7) | 6.437 GB (10) |
| build cache | 1.718 GB | 2.08 GB |
| memory (`docker stats`) | — | jenkins 768 MiB / 1.5 GiB limit, eduforecast-test 130 MiB, registry 32 MiB |
| jenkins_home volume | — | 277 MB |
