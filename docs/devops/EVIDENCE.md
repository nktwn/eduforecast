# Evidence

All numbers below come from command output or the Jenkins API. Host: MacBook Apple M2, arm64, 8 GB RAM;
Docker Desktop 4.37.2 (engine 27.4.0), Docker VM memory 3.83 GiB. Full console logs: [ci-logs/](ci-logs/).
Screenshots with captions: [screenshots/README.md](screenshots/README.md).

Two phases:

1. **GitHub-sourced runs (2026-11-06)**: the job reads `https://github.com/nktwn/eduforecast.git`.
   These are the runs that prove the assignment.
2. **Pre-publication validation from a local mirror (2026-10-30)**: before anything was pushed, Jenkins
   read the bare mirror `file:///mirror/eduforecast.git` (`scripts/devops/sync_mirror.sh`).

## 1. GitHub-sourced runs (2026-11-06)

Times UTC. Tests: passed / failed / skipped from the Jenkins JUnit report. Logs: `ci-logs/github-*.txt`.

| branch #build | commit | trigger | result | duration | tests | image / tags | notes |
|---|---|---|---|---|---|---|---|
| devops/docker-jenkins #1 | 3e895c47 | Branch indexing, 13:23:00 | ABORTED (all stages ran green) | 75.1 s | 123 / 0 / 7 | `eduforecast:3e895c47`, `devops-docker-jenkins-build-1` | duplicate: indexing at Jenkins start-up plus a manual scan 6 s later; the second queue item cancelled this run after it finished (`Queue task was cancelled`) |
| devops/docker-jenkins #2 | 3e895c47 | Branch indexing, 13:23:20 | SUCCESS | 108.0 s | 123 / 0 / 7 | `eduforecast:3e895c47`, `devops-docker-jenkins-build-2` | merge gate for PR #1; no deploy (not `main`) |
| main #7 | 0a0518da (merge commit of PR #1) | Branch indexing, 13:29:15 = **39 s after the merge** (13:28:36), no click | SUCCESS | 60.1 s | 123 / 0 / 7 | `eduforecast:0a0518da`, `build-7`, `latest` | deploy `eduforecast:a3da0b9b -> eduforecast:0a0518da (status healthy, health ok)` |
| ci-failure-demo #6 | 1838cc01 (deliberately failing test) | Branch indexing, 13:33:16 = 90 s after `git push` (13:31:46) | **FAILURE at Unit tests** | 26.9 s | 122 / **1** / 7 | **none** | Build image, Smoke test, Push image, Deploy skipped; branch deleted afterwards |
| main #8 | 0a0518da | Started by user admin, `PUSH_IMAGE=true`, `REGISTRY_IMAGE=localhost:5000/eduforecast` | SUCCESS | 55.4 s | 123 / 0 / 7 | `0a0518da`, `build-8`, `latest` pushed | Push image 2.6 s; deploy `eduforecast:0a0518da -> eduforecast:0a0518da` |
| docs/devops-evidence #1 | b04cb6f6 | Branch indexing, 13:53:17 = 112 s after `git push` (13:51:25), no click | SUCCESS | 45.5 s | 123 / 0 / 7 | `docs-devops-evidence-build-1` | evidence PR #2, one build for the pushed commit |

The table is extended by the build of the evidence PR and its merge (see `docs/devops/REPORT_FACTS.md`).

### Stages of main #7 (from `wfapi/describe`)

| stage | status | duration |
|---|---|---|
| Declarative: Checkout SCM | SUCCESS | 8.7 s |
| Checkout | SUCCESS | 0.9 s |
| Build test image | SUCCESS | 5.8 s (layers cached) |
| Lint | SUCCESS | 1.0 s |
| Unit tests | SUCCESS | 17.8 s (pytest 10–11 s, coverage 43 %) |
| Build image | SUCCESS | 4.9 s (layers cached) |
| Smoke test | SUCCESS | 10.1 s (health, uid 10001, no `.env`, 12/12 pages) |
| Push image | NOT_EXECUTED (`PUSH_IMAGE=false`) | — |
| Deploy to test server | SUCCESS | 6.6 s |

### Negative proof

red commit: 1838cc01629d62e520ae765634fa09077894cf9f

- Change: `tests/test_ui_theme.py:33` expected `"1 234 568"` instead of `"1 234 567"`; branch `ci-failure-demo` created from `main`, pushed, never merged.
- Console (`ci-logs/github-ci-failure-demo-6.txt`): `1 failed, 122 passed, 7 skipped`, `pytest exit code: 1`, then `Stage "Build image" skipped due to earlier failure(s)` (same for Smoke test, Push image, Deploy to test server), `Finished: FAILURE`.
- `docker images | grep 1838cc01` → nothing: no runtime image for the failing commit. The test server kept `eduforecast:0a0518da`.
- Jenkins Stage View and even `wfapi/describe` report the skipped stages as `FAILED` with 21–24 ms; the console shows they were skipped (screenshots 09–11).
- Afterwards: `git push origin --delete ci-failure-demo`; GitHub API `/branches/ci-failure-demo` → 404; `/compare/1838cc01...main` → `behind` (the commit is not in `main`).

### Deployment and registry

```
$ curl -s http://127.0.0.1:8502/_stcore/health
ok
$ docker ps --filter name=eduforecast-test --format '{{.Names}} {{.Image}} {{.Status}} {{.Ports}}'
eduforecast-test eduforecast:0a0518da Up 24 seconds (healthy) 127.0.0.1:8502->8501/tcp
$ docker inspect -f '{{index .Config.Labels "eduforecast.revision"}}' eduforecast-test
0a0518da9d84da2df0447be11a22655672128783
$ curl -s http://127.0.0.1:5000/v2/eduforecast/tags/list
{"name":"eduforecast","tags":["build-4","build-8","0a0518da","latest","39a3c2e4"]}
```

### Runtime image `eduforecast:0a0518da`

| check | result |
|---|---|
| user | `app`; `docker exec eduforecast-test id` → `uid=10001(app) gid=10001(app)` |
| HEALTHCHECK | `python -c ... urlopen('http://127.0.0.1:8501/_stcore/health')`; state `healthy` |
| OCI labels | `revision=0a0518da9d84da2df0447be11a22655672128783`, `source=https://github.com/nktwn/eduforecast`, `created=2026-11-06T13:36:37Z` |
| `docker history --no-trunc` | build args only `GIT_SHA`, `BUILD_DATE`, `SOURCE_URL`; lines matching password/token/secret/api_key/gsk_/sk-ant-: 0 |
| `.env` / `secrets.toml` under `/app` | 0 files |
| size | `.Size` 357,629,371 B; `docker images` 1.64 GB (containerd store, layers shared between tags); arm64 |
| exposed port | 8501/tcp, published as `127.0.0.1:8502` |

### Jenkins

| check | result |
|---|---|
| version | `X-Jenkins: 2.580.2`, OpenJDK 21.0.13, Docker CLI 29.9.2 → daemon 27.4.0 |
| plugins | 15 pinned in `jenkins/plugins.txt`, 79 installed with dependencies |
| security | admin login HTTP 200; anonymous `GET /api/json` HTTP 403; published on 127.0.0.1:8080 only |
| job source | `config.xml` → `<remote>https://github.com/nktwn/eduforecast.git</remote>` |
| Jenkinsfile linter | `POST /pipeline-model-converter/validate` → `Jenkinsfile successfully validated.` |

## 2. Pre-publication validation from a local mirror (2026-10-30)

Jenkins read `file:///mirror/eduforecast.git`; the mirror's `main` = branch `devops/docker-jenkins` at that time.

Times are local (UTC+5). Logs: `ci-logs/jenkins-*.txt`. Tests: passed / failed / skipped from the Jenkins JUnit report.
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
| ci-failure-demo #4 | 366fdf8 | Started by an SCM change (pollSCM; mirror branch moved to the current head to verify branch-prefixed tags) | SUCCESS | 39.5 s | 123 / 0 / 7 | — | 366fdf8c, ci-failure-demo-build-4 | tag fix verified |
| ci-failure-demo #5 | 366fdf8 | Branch indexing (20:08:45) | SUCCESS | 35.1 s | 123 / 0 / 7 | — | ci-failure-demo-build-5 | duplicate of #4 (second trigger, same commit) |
| main #6 | a3da0b9 | Branch indexing (20:10:16) | SUCCESS | 51 s | 123 / 0 / 7 | — | a3da0b9b, build-6, latest | last mirror run; deploy `366fdf8c -> a3da0b9b` |

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

## Docker image (Phase 1, built by hand before Jenkins, 2026-10-30)

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

## Jenkins (Phase 2, 2026-10-30)

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
| 9 | (2026-11-06) the first build of the published branch ran twice (#1 and #2, same commit) | Jenkins re-indexes the repository when JCasC/Job DSL re-applies the job at start-up; a manual "Scan Multibranch Pipeline Now" 6 s later scheduled the branch again before #1 had recorded its revision. Not a trigger defect: after that, every commit (merge → main #7, failing commit → ci-failure-demo #6, evidence PR) was built once. Lesson: do not scan by hand right after recreating Jenkins |
| 10 | no `gh` CLI and no GitHub token on the host | the PR was opened and merged by the owner in the browser ("Create a merge commit"); the title and body were added afterwards |
| 11 | Stage View shows stages skipped after a failure as red "failed" cells | kept Jenkins as is; the console screenshots 10–11 and `ci-logs/github-ci-failure-demo-6.txt` prove the stages were skipped and no image was built |
| 12 | screenshot tooling: a locator on console text centred the whole console `<pre>`; GitHub pages embed file names in `<script>` JSON; the Streamlit deep link `/academic` showed "Page not found" | text-node search with `scrollTo` that skips `script`/hidden nodes; the app page is opened through the sidebar |

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
