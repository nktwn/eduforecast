# Screenshots

Captured headlessly by `scripts/devops/jenkins_screenshots.py --main-build 4 --red-build 2`
(Playwright Chromium, 1440×900). The login page and the password are never captured.

| file | shows |
|---|---|
| `01_dashboard.png` | Jenkins dashboard with the `eduforecast` multibranch job |
| `02_stage_view_main.png` | Stage View of branch `main`: builds #1–#4 green, all stages incl. Push and Deploy |
| `03_console_stages.png` | console of main #4 (timestamps) during the Smoke test stage: `page_smoke.py` rendering each page `OK` inside the container |
| `04_test_result.png` | Test Result of main #4: 123 passed, 7 skipped |
| `05_test_trend.png` | branch page with the Test Result Trend chart and last successful artifacts |
| `06_red_run_stage_view.png` | `ci-failure-demo`: #2 red at Unit tests, later stages not run; #3 green after the fix |
| `07_red_run_test_result.png` | Test Result of the red run: 1 failure (`test_russian_format`) |
| `08_artifacts.png` | archived artifacts: `junit.xml`, `coverage.xml`, `image-info.txt`, `pip-freeze.txt` |
| `09_multibranch_job.png` | multibranch job with branches `main` and `ci-failure-demo` |
| `10_app_test_server.png` | the deployed app at http://localhost:8502 (Command Center, no LLM key, no data) |

## To capture by hand (optional)

- Terminal: `docker ps` showing `eduforecast-jenkins`, `eduforecast-test`, `eduforecast-registry`.
- Terminal: `curl -s http://localhost:8502/_stcore/health` → `ok`.
- Terminal: `curl -s http://127.0.0.1:5000/v2/eduforecast/tags/list`.
- Docker Desktop → Images: `eduforecast` tags.
- After pushing to GitHub: the job scanning `https://github.com/nktwn/eduforecast.git`.
