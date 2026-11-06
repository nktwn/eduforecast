# Report facts: Assignment 5 (DevOps and CI/CD), EduForecast-SIS

Facts for the person writing the 1–2 page report. Every number comes from command output, the Jenkins API
or the GitHub API; sources are named. Details: [EVIDENCE.md](EVIDENCE.md), screenshots:
[screenshots/README.md](screenshots/README.md), console logs: [ci-logs/](ci-logs/).

## 1. What was built

| requirement | implementation | where |
|---|---|---|
| Python research project on GitHub | EduForecast-SIS (Streamlit analytics app + research code), public repo | https://github.com/nktwn/eduforecast |
| Dockerfile | multi-stage: `base` (python:3.12.13-slim-bookworm + pinned deps), `test` (+ git, ruff, pytest-cov, full tree), `runtime` (default; non-root uid 10001, OCI labels, HEALTHCHECK, no datasets, no secrets); allowlist `.dockerignore` | `Dockerfile`, `.dockerignore` |
| Jenkins server | Jenkins LTS 2.580.2 (JDK 21) in Docker on the laptop, 127.0.0.1:8080, configured as code (JCasC + Job DSL, no setup wizard), 15 pinned plugins | `jenkins/` |
| CI pipeline | declarative `Jenkinsfile`: Checkout → Build test image → Lint → Unit tests (JUnit + coverage) → Build image → Smoke test → Push image (optional) → Deploy to test server (main only) | `Jenkinsfile` |
| tests on every commit | multibranch job scans GitHub every 2 minutes; each new commit of each branch is built once | `jenkins/casc/jenkins.yaml` |
| image push (optional) | parameter `PUSH_IMAGE`; done to a local `registry:2.8.3` (localhost:5000); Docker Hub supported via a Jenkins credential but not executed (no account token configured) | `Jenkinsfile` stage Push image |
| CD (bonus) | on `main`, the pipeline replaces the container `eduforecast-test` (127.0.0.1:8502) with the new image and checks its health | `Jenkinsfile` stage Deploy to test server |
| Kubernetes (optional) | k3d manifests and scripts written, **not executed** | `k8s/`, `scripts/devops/k3d_*.sh` |

## 2. Steps taken, in order

1. **Dockerfile and image** (2026-10-30). Traced which files the pages read at runtime (audit hook) and copied only those into the runtime stage. Built and tested by hand:
   `make docker-test` (`docker build --target test`, pytest in the container), `make docker-build`, `scripts/devops/smoke_container.sh eduforecast:dev`.
2. **Jenkins as code** (2026-10-30). `jenkins/Dockerfile` (LTS image + Docker CLI + plugins), `jenkins/docker-compose.yml` (127.0.0.1:8080, host Docker socket, memory limit 1.5 GiB), `jenkins/casc/jenkins.yaml` (admin user from env, no anonymous read, multibranch job). Start: `make jenkins-env && make jenkins-up`.
3. **Jenkinsfile** (2026-10-30): eight stages; JUnit and coverage archived; images tagged `<sha>`, `build-N` (`<branch>-build-N` off main), `latest` (main).
4. **Validation before publishing** (2026-10-30): nothing was pushed yet, so Jenkins read a local bare mirror (`scripts/devops/sync_mirror.sh`, `GIT_REPO_URL=file:///mirror/eduforecast.git`). 6 green main runs, a deliberately failing branch, a registry push and deployments (EVIDENCE.md section 2).
5. **Audit** (2026-11-06): an independent read-only audit found that nothing DevOps-related was on GitHub (Jenkinsfile and Dockerfile HTTP 404), the image depended on `data/aitu/` that was not on GitHub, and two triggers built the same commit twice.
6. **Owner decisions** (2026-11-06): publish `data/aitu/` and the other unpublished commits as they are (Plan A); confirm the push after a pre-publication scan (`scripts/devops/prepush_audit.sh`: 0 secret patterns, 0 tracked `.env`, no file > 500 KB).
7. **Fixes before publishing** (5 commits): removed `pollSCM` from the Jenkinsfile (single trigger); `jenkins_env.sh` defaults to the GitHub URL; README DevOps section; screenshot script; `scripts/devops/final_check.sh`.
8. **Publish**: `git push -u origin devops/docker-jenkins` (46 commits); PR #1 opened in the browser.
9. **Switch Jenkins to GitHub**: `GIT_REPO_URL=https://github.com/nktwn/eduforecast.git` in `jenkins/.env.jenkins`, `docker compose -f jenkins/docker-compose.yml up -d --force-recreate jenkins`; job source verified via `config.xml`.
10. **Branch build from GitHub**: devops/docker-jenkins #2 SUCCESS (108 s) → merge gate passed.
11. **Merge** PR #1 with a merge commit (`0a0518da`, 2 parents). Jenkins built `main` **#7 automatically 39 s after the merge**: all stages green, deployed `eduforecast:0a0518da` to 8502.
12. **Negative test from GitHub**: branch `ci-failure-demo` with one wrong expected value → **#6 FAILURE at Unit tests 90 s after the push**, Build image / Smoke / Push / Deploy skipped, no image; branch deleted, commit never on main.
13. **Registry push**: main #8 with `PUSH_IMAGE=true`, `REGISTRY_IMAGE=localhost:5000/eduforecast` → tags `0a0518da`, `build-8`, `latest` in the registry.
14. **Evidence**: screenshots from the GitHub-sourced runs, logs, this file; PR #2 (`docs/devops-evidence` → `main`), merged with a merge commit; annotated tag `assignment5-final` on main.

## 3. Design decisions and why

| decision | why |
|---|---|
| multi-stage Dockerfile (base / test / runtime) | tests run in the same dependency layer as the app, but the runtime image contains no tests, git or linters; base layers are cached, so a code change rebuilds in seconds |
| non-root user, HEALTHCHECK, OCI labels | least privilege; Docker and the pipeline can wait for "healthy"; every image says which commit it came from (`org.opencontainers.image.revision`) |
| no datasets, no secrets in the image | the repo is public; the app works in "no data / briefing" mode; `.env*` is excluded from the build context |
| tests inside containers, not in the Jenkins JVM container | the Jenkins image needs no Python; CI and local runs use the same image |
| Jenkins configured as code (JCasC + Job DSL), pinned plugins | reproducible from the repo: delete the container, run `make jenkins-up`, get the same Jenkins and job; no clicking in the UI |
| multibranch pipeline | every branch (including a failing demo branch) is discovered and built automatically; only `main` deploys |
| one trigger: 2-minute branch scan, no `pollSCM`, no webhook | two triggers built one commit twice; GitHub webhooks cannot reach a Jenkins bound to 127.0.0.1 (would need a public URL or tunnel) |
| validate from a local mirror before publishing | the repo is public; the pipeline was proven before any commit became public, and the push happened only after an explicit decision |
| CD to a local test container instead of Kubernetes | fits the 3.8 GiB Docker VM next to Jenkins; Kubernetes manifests are provided but k3d was not installed (owner did not want extra tools) |
| local registry instead of Docker Hub | proves the push step without an account token on the machine; Docker Hub is one credential away |

## 4. Difficulties and how they were solved

| # | problem | solution |
|---|---|---|
| 1 | `FileNotFoundError: 'git'` in the test image (a test calls `git ls-files`) | install git in the `test` stage only |
| 2 | Jenkins did not start: `UnknownAttributesException ... excludeClientIPFromCrumb` | removed the outdated JCasC attribute (default CSRF protection stays) |
| 3 | checkout from the mirror: `unable to open loose object ... Permission denied` | the mirror had hard-linked objects that Docker Desktop could not read; re-cloned with `git clone --no-local` |
| 4 | `POST /job/.../build` → HTTP 400 | parameterized jobs need `/buildWithParameters` |
| 5 | the same commit built twice (mirror runs main #2/#3, ci-failure-demo #4/#5) | `pollSCM` and the branch scan both fired; `pollSCM` removed |
| 6 | `build-N` image tags of different branches overwrote each other | non-main branches get `<branch>-build-N` |
| 7 | disk and memory: free disk fell from 19 to 9 GiB on 2026-10-30 (Docker images, cache); Docker VM 3.8 GiB | removed only own obsolete tags after each phase; Jenkins limited to 1.5 GiB (heap 768 MiB), one executor |
| 8 | Stage View marks stages skipped after a failure as red "failed" | documented; the console log proves `skipped due to earlier failure(s)` and that no image was built |
| 9 | the image copies `data/aitu/` which was not on GitHub | owner decision Plan A: the data were published with the branch, so a clean GitHub checkout builds |
| 10 | first build of the published branch ran twice | start-up indexing plus a manual scan 6 s apart; afterwards every commit built once |
| 11 | no `gh` CLI / token on the machine | the owner opened and merged the PRs in the browser with "Create a merge commit" |

## 5. Numbers

| item | value | source |
|---|---|---|
| tests in CI | 130 collected: 123 passed, 7 skipped (need local datasets not in git) | JUnit report, main #7 |
| red run | 1 failed (`test_russian_format`), 122 passed, 7 skipped | ci-failure-demo #6 |
| coverage | 43 % (`--cov=app --cov=src`, 7,209 statements) | console main #7 |
| pipeline duration | 55–60 s for main (#7 60.1 s, #8 55.4 s), 108 s for the first branch build | Jenkins API |
| stage times main #7 | test image 5.8 s, lint 1.0 s, unit tests 17.8 s, runtime image 4.9 s, smoke 10.1 s, deploy 6.6 s | `wfapi/describe` |
| commit → build start | 39 s (merge → main #7), 90 s (push → ci-failure-demo #6); scan interval 2 min | Jenkins/GitHub timestamps |
| runtime image | `.Size` 357,629,371 B; `docker images` 1.64 GB; arm64 | `docker image inspect` |
| test image | 1.81 GB (`docker images`, 2026-10-30) | EVIDENCE.md |
| cold build | test target 175 s with an empty pip cache (2026-10-30); Jenkins controller image 520 s | EVIDENCE.md |
| cached build | runtime target 3–5 s; test target 2–6 s in CI | EVIDENCE.md, main #7 |
| site-packages | 1.1 GB (llvmlite, pyarrow, scipy, pandas, plotly); app code 1.4 MB | EVIDENCE.md |
| Jenkins | 2.580.2 LTS, OpenJDK 21.0.13, 15 pinned / 79 installed plugins, Docker CLI 29.9.2 → engine 27.4.0 | API header, `java -version` |
| security checks | anonymous `GET /api/json` 403; admin 200; ports bound to 127.0.0.1 | curl |
| host | MacBook Apple M2, 8 GB RAM, Docker VM 3.83 GiB; Docker.raw ~32 GB; free disk ~11 GiB during the work | `docker info`, `df -h` |

Full table of GitHub-sourced runs: EVIDENCE.md section 1; mirror runs: section 2.

## 6. Links

| what | link |
|---|---|
| repository | https://github.com/nktwn/eduforecast |
| Jenkinsfile | https://github.com/nktwn/eduforecast/blob/main/Jenkinsfile |
| Dockerfile | https://github.com/nktwn/eduforecast/blob/main/Dockerfile |
| Jenkins as code | https://github.com/nktwn/eduforecast/tree/main/jenkins |
| DevOps docs | https://github.com/nktwn/eduforecast/tree/main/docs/devops |
| PR #1 (DevOps, merged) | https://github.com/nktwn/eduforecast/pull/1 |
| merge commit of PR #1 | https://github.com/nktwn/eduforecast/commit/0a0518da9d84da2df0447be11a22655672128783 |
| PR #2 (evidence) | https://github.com/nktwn/eduforecast/pull/2 |
| final tag | https://github.com/nktwn/eduforecast/tree/assignment5-final |
| local Jenkins | http://localhost:8080 (user `admin`, password in the git-ignored `jenkins/.env.jenkins`) |
| local test server | http://localhost:8502 |
| local registry | http://127.0.0.1:5000/v2/eduforecast/tags/list |

## 7. Limitations

- Jenkins runs on the laptop, not on a server; it is reachable only from that machine, so "every commit" means a 2-minute polling scan, not a webhook.
- Docker Hub push is implemented (credential `dockerhub-credentials`) but was not executed; the local registry proves the push step.
- Kubernetes manifests are not executed (k3d not installed).
- The runtime image is large (1.64 GB) because of the scientific stack (Prophet/cmdstan, LightGBM, SHAP, pyarrow).
- Coverage is 43 %; 7 tests are skipped in CI because they need datasets that are not in git.
- Jenkins mounts the Docker socket and runs as root: root-equivalent on the Docker host; acceptable only for a local study setup.
- Images are arm64 only (Apple Silicon); a multi-arch `buildx` recipe is in RUNBOOK.md but was not run.

## 8. Conclusions

- The project builds, tests and deploys from the public GitHub repository without manual steps: a merge into `main` produced a green build and a new test deployment 39 s later.
- A failing unit test stops the pipeline before an image is built, so a broken commit cannot reach the test server.
- Configuration as code made Jenkins reproducible and the switch from the mirror to GitHub a one-line change.
- The main practical costs were disk space and memory on an 8 GB laptop, and small Jenkins details (trigger duplication, outdated JCasC attributes, Stage View rendering).
