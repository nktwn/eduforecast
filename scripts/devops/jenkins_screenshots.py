"""Capture Jenkins, test-deployment, registry and GitHub screenshots for the DevOps report.

Playwright (headless Chromium), viewport 1440x900. Logs in to Jenkins with the credentials
from jenkins/.env.jenkins (never printed; the login page itself is never captured) and saves
PNGs to docs/devops/screenshots/. GitHub pages are public and opened without login.

Usage:
  python scripts/devops/jenkins_screenshots.py --main-build N --red-build M [--pr K]
         [--red-branch ci-failure-demo] [--only 06,07]

Notes:
  * Stage View renders stages that were skipped after a failure as red "failed" cells.
    The console screenshots (07, 08) show the real outcome: 'Stage "Build image" skipped
    due to earlier failure(s)'.
  * The app screenshot uses the "Academic overview" page (OULAD demo, no datasets in the
    image) rather than the Command Center.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "devops" / "screenshots"
JENKINS = "http://localhost:8080"
APP = "http://localhost:8502"
REGISTRY = "http://127.0.0.1:5000"
GITHUB = "https://github.com/nktwn/eduforecast"
JOB = f"{JENKINS}/job/eduforecast"


def read_env(path: Path) -> dict[str, str]:
    env = {}
    for line in path.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def shot_list(a: argparse.Namespace) -> list[tuple[str, str, str | None, bool]]:
    """(file, url, text/selector to scroll to, needs Jenkins login)."""
    main = f"{JOB}/job/main"
    mb = f"{main}/{a.main_build}"
    red = f"{JOB}/job/{a.red_branch}"
    rb = f"{red}/{a.red_build}"
    shots = [
        ("01_dashboard.png", f"{JENKINS}/", None, True),
        ("02_job_github_source.png", f"{JOB}/configure", 'input[value*="github.com/nktwn/eduforecast"]', True),
        ("03_branches.png", f"{JOB}/", None, True),
        ("04_stage_view_main.png", f"{main}/", "#pipeline-box, .stage-view, table.jobsTable", True),
        ("05_console_main_checkout.png", f"{mb}/console", "text=Obtained Jenkinsfile from", True),
        ("06_console_main_deploy.png", f"{mb}/console", "text=deploy: test server URL", True),
        ("07_test_result_main.png", f"{mb}/testReport/", None, True),
        ("08_test_trend_artifacts.png", f"{main}/", "text=Test Result Trend", True),
        ("09_red_stage_view.png", f"{red}/", "#pipeline-box, .stage-view, table.jobsTable", True),
        ("10_red_console_skipped.png", f"{rb}/console", 'text=Stage "Build image" skipped', True),
        ("11_red_test_result.png", f"{rb}/testReport/", None, True),
        ("12_artifacts_main.png", f"{mb}/artifact/reports/", None, True),
        ("13_app_test_server.png", f"{APP}/academic", None, False),
        ("14_registry_tags.png", f"{REGISTRY}/v2/eduforecast/tags/list", None, False),
        ("15_github_repo.png", f"{GITHUB}", "text=Jenkinsfile", False),
    ]
    if a.pr:
        shots.append(("16_github_pr_merged.png", f"{GITHUB}/pull/{a.pr}", None, False))
    if a.only:
        keep = {p.strip() for p in a.only.split(",")}
        shots = [s for s in shots if s[0][:2] in keep]
    return shots


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--main-build", type=int, required=True)
    ap.add_argument("--red-branch", default="ci-failure-demo")
    ap.add_argument("--red-build", type=int, required=True)
    ap.add_argument("--pr", type=int, default=0, help="GitHub pull request number")
    ap.add_argument("--only", default="", help="comma-separated two-digit prefixes")
    args = ap.parse_args()
    env = read_env(ROOT / "jenkins" / ".env.jenkins")
    OUT.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1,
                                timezone_id="Asia/Almaty", locale="en-US")
        page.goto(f"{JENKINS}/login")
        page.fill("input[name=j_username]", env["JENKINS_ADMIN_ID"])
        page.fill("input[name=j_password]", env["JENKINS_ADMIN_PASSWORD"])
        page.click("button[name=Submit], input[name=Submit]")
        page.wait_for_load_state("networkidle")
        if "/login" in page.url:
            raise SystemExit("login failed")
        for name, url, anchor, _ in shot_list(args):
            page.goto(url)
            page.wait_for_load_state("networkidle")
            if "/login" in page.url:
                raise SystemExit(f"redirected to login for {url}; nothing saved")
            if url.startswith(APP):
                page.wait_for_timeout(8000)  # Streamlit renders over a websocket
            if anchor:
                try:
                    page.locator(anchor).first.scroll_into_view_if_needed(timeout=5000)
                except Exception:
                    print(f"  note: anchor not found on {url}: {anchor}")
            page.wait_for_timeout(800)
            page.screenshot(path=str(OUT / name))
            print(f"saved {name} <- {url}")
        browser.close()


if __name__ == "__main__":
    main()
