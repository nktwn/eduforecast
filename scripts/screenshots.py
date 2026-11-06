"""Playwright screenshots of every page at 1440 and 390 px, light and dark, with QA checks.

  python scripts/screenshots.py [--port 8611] [--ask]     # starts streamlit, writes docs/screenshots/v2/

Checks per screenshot: browser console errors, horizontal scroll, clipped text (elements whose content
is wider than the box while overflow is hidden), WCAG contrast of visible text (computed colors).
Results: docs/screenshots/v2/qa.json and qa.md.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "screenshots" / "v2"
PAGES = [("command-center", "", "01_command_center"), ("academic", "academic", "02_academic_overview"),
         ("students", "Students", "03_academic_students"), ("analytics", "Analytics", "04_academic_analytics"),
         ("research", "Research", "05_research"), ("finance", "Finance", "06_finance"),
         ("international", "international", "07_international"), ("upbringing", "upbringing", "08_upbringing"),
         ("advisor", "AI_Advisor", "09_advisor"), ("verified", "verified", "10_verified"),
         ("settings", "settings", "11_settings")]
WIDTHS = {"desktop": 1440, "mobile": 390}

CHECK_JS = r"""
() => {
  const lum = (c) => { const m = c.match(/[\d.]+/g); if (!m) return null; const [r,g,b] = m.slice(0,3).map(x => {
      x = x/255; return x <= 0.03928 ? x/12.92 : Math.pow((x+0.055)/1.055, 2.4); });
      return 0.2126*r + 0.7152*g + 0.0722*b; };
  const alpha = (c) => { const m = c.match(/[\d.]+/g); return m && m.length > 3 ? parseFloat(m[3]) : 1; };
  const bgOf = (el) => { while (el) { const c = getComputedStyle(el).backgroundColor;
      if (c && alpha(c) > 0.5) return c; el = el.parentElement; } return getComputedStyle(document.body).backgroundColor; };
  const main = document.querySelector('[data-testid="stMain"]') || document.body;
  const low = [], clipped = [];
  for (const el of main.querySelectorAll('p, span, div, li, h1, h2, h3, h4, label, button, code, b, td, th')) {
    const own = [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim().length > 1);
    if (!own) continue;
    const r = el.getBoundingClientRect(); if (r.width === 0 || r.height === 0) continue;
    const st = getComputedStyle(el); if (st.visibility === 'hidden' || st.display === 'none') continue;
    const fg = st.color, bg = bgOf(el); const lf = lum(fg), lb = lum(bg); if (lf === null || lb === null) continue;
    const ratio = (Math.max(lf, lb) + 0.05) / (Math.min(lf, lb) + 0.05);
    const size = parseFloat(st.fontSize), bold = parseInt(st.fontWeight) >= 700;
    const need = (size >= 24 || (size >= 18.66 && bold)) ? 3 : 4.5;
    if (ratio < need) low.push({text: el.textContent.trim().slice(0, 60), ratio: +ratio.toFixed(2), fg, bg});
    if ((st.overflow === 'hidden' || st.textOverflow === 'ellipsis') && el.scrollWidth > el.clientWidth + 2)
      clipped.push(el.textContent.trim().slice(0, 60));
  }
  return {hscroll: document.documentElement.scrollWidth > window.innerWidth + 1,
          scrollWidth: document.documentElement.scrollWidth, innerWidth: window.innerWidth,
          low_contrast: low.slice(0, 15), n_low: low.length, clipped: clipped.slice(0, 10)};
}
"""


def wait_ready(page, extra=2.5):
    page.wait_for_selector('[data-testid="stMain"] h1', timeout=180000)
    page.wait_for_function("""() => { const w = document.querySelector('[data-testid="stStatusWidget"]');
                              return !w || !/Running|Выполн/.test(w.innerText); }""", timeout=180000)
    time.sleep(extra)


def shot(page, path, width):
    """Streamlit scrolls an inner container: grow the viewport to the content height, then capture."""
    h = page.evaluate("""() => { const m = document.querySelector('[data-testid="stMain"]');
                                 const c = m ? m.scrollHeight : 0;
                                 const s = document.querySelector('[data-testid="stSidebarContent"]');
                                 return Math.max(c, s ? s.scrollHeight : 0, 900); }""")
    page.set_viewport_size({"width": width, "height": min(int(h) + 40, 7000)})
    time.sleep(1.2)
    page.screenshot(path=str(path), full_page=True)
    page.set_viewport_size({"width": width, "height": 900})
    from PIL import Image  # 256-color palette keeps UI text sharp and the files small for git
    Image.open(path).convert("RGB").quantize(colors=256, method=Image.Quantize.MEDIANCUT,
                                             dither=Image.Dither.NONE).save(path, optimize=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8611)
    ap.add_argument("--ask", action="store_true", help="ask the advisor one live question for a screenshot")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    server = subprocess.Popen([sys.executable, "-m", "streamlit", "run", "app/main.py", "--server.port",
                              str(args.port), "--server.headless", "true"], cwd=ROOT,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://localhost:{args.port}"
    report = []
    try:
        time.sleep(6)
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            for theme in ("light", "dark"):
                for device, width in WIDTHS.items():
                    ctx = browser.new_context(viewport={"width": width, "height": 900}, color_scheme=theme,
                                              device_scale_factor=1 if device == "desktop" else 2)
                    for key, path, name in PAGES:
                        page = ctx.new_page()  # a fresh tab per page: no requests left over from the previous one
                        errors = []
                        page.on("console", lambda m, e=errors: e.append(m.text) if m.type == "error" else None)
                        page.on("pageerror", lambda x, e=errors: e.append(str(x)))
                        page.on("response", lambda r, e=errors: e.append(f"HTTP {r.status} {r.url}")
                                if r.status >= 400 else None)
                        page.goto(f"{base}/{path}")
                        wait_ready(page)
                        if key == "advisor":
                            btn = page.get_by_role("button", name="Сформировать брифинг")
                            if btn.count():
                                btn.first.click()
                                wait_ready(page, 2)
                        qa = page.evaluate(CHECK_JS)
                        file = OUT / f"{name}_{device}_{theme}.png"
                        shot(page, file, width)
                        report.append({"page": key, "device": device, "theme": theme, "file": file.name,
                                       "console_errors": list(errors), **qa})
                        print(name, device, theme, "hscroll" if qa["hscroll"] else "", f"low={qa['n_low']}",
                              f"clipped={len(qa['clipped'])}", f"errors={len(errors)}", flush=True)
                        page.close()
                    if args.ask and theme == "light" and device == "desktop":
                        page = ctx.new_page()
                        page.goto(f"{base}/AI_Advisor")
                        wait_ready(page)
                        page.get_by_role("tab", name="Вопросы").click()
                        page.get_by_role("button", name="Как растёт число публикаций AITU?").first.click() \
                            if page.get_by_role("button", name="Как растёт число публикаций AITU?").count() else None
                        box = page.get_by_placeholder("Вопрос советнику")
                        box.fill("Каким результатам системы можно доверять?")
                        box.press("Enter")
                        wait_ready(page, 6)
                        shot(page, OUT / "12_advisor_question_desktop_light.png", 1440)
                    ctx.close()
            # in-app navigation (sidebar links) — how users move between pages
            ctx = browser.new_context(viewport={"width": 1440, "height": 900})
            page = ctx.new_page()
            nav_errors = []
            page.on("console", lambda m: nav_errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda x: nav_errors.append(str(x)))
            page.goto(base)
            wait_ready(page)
            titles = ["Академический: обзор", "Академический: студенты", "Академический: аналитика", "Научный",
                      "Финансы", "Международный", "Воспитательный", "ИИ-советник", "Что проверено",
                      "Настройки и состояние", "Командный центр"]
            for t in titles:
                page.get_by_role("link", name=t).first.click()
                wait_ready(page, 1.5)
            report.append({"page": "in-app navigation", "device": "desktop", "theme": "light", "file": "",
                           "console_errors": nav_errors, "hscroll": False, "n_low": 0, "clipped": [],
                           "low_contrast": [], "scrollWidth": 0, "innerWidth": 1440})
            print("in-app navigation errors:", nav_errors, flush=True)
            ctx.close()
            browser.close()
    finally:
        server.terminate()
        server.wait(timeout=20)
    (OUT / "qa.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    lines = ["| страница | ширина | тема | гориз. прокрутка | обрезанный текст | низкий контраст | ошибки консоли |",
             "|---|---|---|---|---|---|---|"]
    for r in report:
        lines.append(f"| {r['page']} | {r['device']} | {r['theme']} | {'да' if r['hscroll'] else 'нет'} | "
                     f"{len(r['clipped'])} | {r['n_low']} | {len(r['console_errors'])} |")
    (OUT / "qa.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("done", len(report))


if __name__ == "__main__":
    main()
