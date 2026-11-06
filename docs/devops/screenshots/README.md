# Screenshots

All screenshots were taken on 2026-11-06 from builds whose source was the public GitHub repository
`https://github.com/nktwn/eduforecast.git` (not the local mirror used before publication).
Tool: `scripts/devops/jenkins_screenshots.py` (Playwright Chromium, 1440×900):

```bash
.venv/bin/python scripts/devops/jenkins_screenshots.py --main-build 7 --red-build 6 --pr 1
```

No screenshot shows the Jenkins login page, a password or a token. Times in the Jenkins UI are a mix of
UTC and UTC+5 (the timestamper plugin renders part of the console in the browser time zone).
Earlier screenshots from the local-mirror validation (2026-10-30) are in the git history of this folder.

| file | what it proves | build / commit |
|---|---|---|
| `01_dashboard.png` | Jenkins 2.580.2 is running locally; one job `eduforecast`, system message "configured by code (JCasC)" | — |
| `02_job_github_source.png` | the multibranch job reads `https://github.com/nktwn/eduforecast.git`, no credentials (public repo), branch discovery | job configuration |
| `03_branches.png` | branches found in GitHub: `main` (#8 green), `devops/docker-jenkins` (#2 green), `ci-failure-demo` (crossed out: branch deleted after the negative test, last failure #6) | — |
| `04_stage_view_main.png` | Stage View of `main`: #7 (automatic, after the merge) and #8 (manual, `PUSH_IMAGE=true`) green in every stage; #1–#6 are the earlier mirror runs | main #7 `0a0518da`, main #8 `0a0518da` |
| `05_console_main_checkout.png` | console of main #7: `branch=main commit=0a0518da…`, merge commit of PR #1, Docker client 29.9.2 / daemon 27.4.0 | main #7 `0a0518da` |
| `06_console_main_deploy.png` | same console: `page_smoke: 12/12 pages rendered`, `smoke: PASS`, Push skipped by condition, `deploy: eduforecast:a3da0b9b -> eduforecast:0a0518da (status healthy, health ok)` | main #7 `0a0518da` |
| `07_test_result_main.png` | JUnit report: 130 tests, 123 passed, 7 skipped, 0 failed | main #7 |
| `08_test_trend_artifacts.png` | Test Result Trend over builds #1–#8 and the archived artifacts (`coverage.xml`, `image-info.txt`, `junit.xml`, `pip-freeze.txt`) | main |
| `09_red_stage_view.png` | negative test: ci-failure-demo #6 red at Unit tests. Stage View draws the stages that were **skipped** after the failure as red "failed" cells of 21–24 ms; 10 and 11 show what really happened | ci-failure-demo #6 `1838cc01` |
| `10_red_console_failure.png` | console of the red run: `AssertionError` in `tests/test_ui_theme.py:33` (expected value changed on purpose) | ci-failure-demo #6 `1838cc01` |
| `11_red_console_skipped.png` | same console: `Stage "Build image" / "Smoke test" / "Push image" / "Deploy to test server" skipped due to earlier failure(s)`: no runtime image was built for this commit | ci-failure-demo #6 `1838cc01` |
| `12_red_test_result.png` | JUnit report of the red run: 1 failed (`test_russian_format`, regression), 122 passed, 7 skipped | ci-failure-demo #6 |
| `13_artifacts_main.png` | artifacts of main #7 with sizes and times | main #7 |
| `14_app_test_server.png` | the deployed app on `http://localhost:8502`, page "Settings and status": no LLM key, which datasets are present (no financial figures shown) | image `eduforecast:0a0518da` |
| `15_registry_tags.png` | local registry `localhost:5000/eduforecast` tags after main #8: `0a0518da`, `build-8`, `latest` (plus `39a3c2e4`, `build-4` from the mirror validation) | main #8 |
| `16_github_repo.png` | public GitHub `main`: `.dockerignore`, `Dockerfile`, `Jenkinsfile`, `Makefile`, `jenkins/`, `k8s/`, `scripts/` | `0a0518da` |
| `17_github_pr_merged.png` | PR #1 `devops/docker-jenkins` → `main`, merged with a merge commit (46 commits). The PR was opened in the browser with an empty description; title and description were completed after the merge ("edited") | PR #1 |
