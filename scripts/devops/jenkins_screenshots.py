"""Capture Jenkins and test-deployment screenshots for the DevOps report (Playwright, headless).

Logs in with the credentials from jenkins/.env.jenkins (never printed, the login page is not
captured) and saves viewport-sized PNGs to docs/devops/screenshots/.
Usage: python scripts/devops/jenkins_screenshots.py [--main-build N] [--red-build N]
"""
from __future__ import annotations

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "devops" / "screenshots"
JENKINS = "http://localhost:8080"
APP = "http://localhost:8502"
JOB = f"{JENKINS}/job/eduforecast"


def read_env(path: Path) -> dict[str, str]:
    env = {}
    for line in path.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--main-build", type=int, required=True)
    ap.add_argument("--red-branch", default="ci-failure-demo")
    ap.add_argument("--red-build", type=int, required=True)
    args = ap.parse_args()
    env = read_env(ROOT / "jenkins" / ".env.jenkins")
    OUT.mkdir(parents=True, exist_ok=True)
    main_build = f"{JOB}/job/main/{args.main_build}"
    red = f"{JOB}/job/{args.red_branch}"

    shots = [
        ("01_dashboard.png", f"{JENKINS}/", None),
        ("02_stage_view_main.png", f"{JOB}/job/main/", "table.jobsTable, .stage-view, #pipeline-box"),
        ("03_console_stages.png", f"{main_build}/console", "text=smoke: PASS"),
        ("04_test_result.png", f"{main_build}/testReport/", None),
        ("05_test_trend.png", f"{JOB}/job/main/", "text=Test Result Trend"),
        ("06_red_run_stage_view.png", f"{red}/", "table.jobsTable, .stage-view, #pipeline-box"),
        ("07_red_run_test_result.png", f"{red}/{args.red_build}/testReport/", None),
        ("08_artifacts.png", f"{main_build}/artifact/", None),
        ("09_multibranch_job.png", f"{JOB}/", None),
        ("10_app_test_server.png", f"{APP}/", None),
    ]

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
        page.goto(f"{JENKINS}/login")
        page.fill("input[name=j_username]", env["JENKINS_ADMIN_ID"])
        page.fill("input[name=j_password]", env["JENKINS_ADMIN_PASSWORD"])
        page.click("button[name=Submit], input[name=Submit]")
        page.wait_for_load_state("networkidle")
        if "/login" in page.url:
            raise SystemExit("login failed")
        for name, url, anchor in shots:
            page.goto(url)
            page.wait_for_load_state("networkidle")
            if url.startswith(APP):
                page.wait_for_timeout(6000)  # Streamlit renders over a websocket
            if anchor:
                try:
                    page.locator(anchor).first.scroll_into_view_if_needed(timeout=5000)
                except Exception:
                    pass
            page.wait_for_timeout(800)
            page.screenshot(path=str(OUT / name))
            print(f"saved {name} <- {url}")
        browser.close()


if __name__ == "__main__":
    main()
