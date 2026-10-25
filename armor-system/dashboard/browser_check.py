"""Drive the dashboard in a real browser and record what happened (optional; needs `playwright` and Google Chrome).

    .venv/bin/python armor-system/dashboard/browser_check.py            # starts its own server, writes evidence/dashboard_browser_check.json

For every page it records exceptions, 'Artifact not available' messages, chart and table counts and console errors, then
runs an interactive pass (tabs, protocol selector, boundary slider, lazy feature-cache load).
"""
import datetime
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(HERE, "..", "data", "artifacts", "d1", "evidence", "dashboard_browser_check.json")
PAGES = ["1 - Project Overview", "2 - Dataset Explorer", "3 - Data Splitting", "4 - EDA", "5 - Preprocessing", "6 - Data Quality", "7 - Deliverables and Evidence"]


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main():
    from playwright.sync_api import sync_playwright
    port = free_port()
    srv = subprocess.Popen([sys.executable, "-m", "streamlit", "run", "app.py", "--server.port", str(port), "--server.headless", "true", "--browser.gatherUsageStats", "false"],
                           cwd=HERE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            try:
                if urllib.request.urlopen(f"http://127.0.0.1:{port}/_stcore/health", timeout=2).read() == b"ok":
                    break
            except Exception:
                time.sleep(1)
        pages, steps, errs = [], [], []
        with sync_playwright() as p:
            b = p.chromium.launch(channel="chrome", headless=True)
            version = b.version
            pg = b.new_page(viewport={"width": 1440, "height": 1100})
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
            pg.goto(f"http://127.0.0.1:{port}", wait_until="networkidle")
            pg.wait_for_selector("[data-testid=stSidebar]", timeout=30000)

            def settle(label, bucket):
                pg.wait_for_timeout(1800)
                try:
                    pg.wait_for_selector("[data-testid=stStatusWidget]", state="detached", timeout=20000)
                except Exception:
                    pass
                t = pg.inner_text("body")
                bucket.append({"step": label, "exceptions": pg.locator("[data-testid=stException]").count(), "missing_artifact_messages": t.count("Artifact not available"),
                               "charts": pg.locator(".js-plotly-plot").count(), "tables": pg.locator("[data-testid=stDataFrame]").count(), "text_chars": len(t)})

            nav = lambda n: pg.locator("[data-testid=stSidebar]").get_by_text(n, exact=True).first.click()  # noqa: E731
            tab = lambda n: pg.get_by_role("tab", name=n).first.click()  # noqa: E731
            for n in PAGES:
                nav(n)
                settle(n, pages)
            nav(PAGES[1])
            for t in ["Representative records", "Case explorer", "Timestamps and sampling", "Live sample inspector"]:
                tab(t); settle("explorer / " + t, steps)
            pg.get_by_role("button", name="Load feature cache").click(); settle("explorer / feature cache loaded", steps)
            nav(PAGES[2]); settle("splitting / approved", steps)
            sel = pg.locator("[data-testid=stSelectbox]").first
            sel.click(); pg.get_by_text("REJECTED candidate (100 / 26 / 84) - fails hard checks").first.click(); settle("splitting / rejected candidate", steps)
            sel.click(); pg.get_by_text("Official ARMOR reproduction (126 / 84)").first.click(); settle("splitting / official", steps)
            sl = pg.get_by_role("slider").last; sl.scroll_into_view_if_needed(); sl.focus()
            for _ in range(3):
                sl.press("ArrowLeft")
            settle("splitting / boundary slider moved", steps)
            nav(PAGES[3])
            for t in ["Class distribution", "Feature distributions", "Missingness", "Correlation", "Time series", "Incident-aligned", "Variability / outliers", "Train vs validation", "Static figures"]:
                tab(t); settle("eda / " + t, steps)
            nav(PAGES[4])
            for t in ["Raw to prepared example", "Scaling statistics", "Structural masks and indicators", "Before / after", "Windowing and counts", "Validation evidence"]:
                tab(t); settle("preprocessing / " + t, steps)
            nav(PAGES[5]); settle("quality", steps)
            nav(PAGES[6]); settle("evidence", steps)
            b.close()
        rows = pages + steps
        result = {"checked_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "browser": f"Google Chrome (headless) {version}",
                  "pages_checked": len(pages), "interactive_steps": len(steps), "pages": pages, "steps": steps, "console_or_page_errors": errs[:10],
                  "all_clear": all(r["exceptions"] == 0 and r["missing_artifact_messages"] == 0 for r in rows) and not errs,
                  "git_head": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=REPO).stdout.strip()}
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w") as fh:
            json.dump(result, fh, indent=2)
            fh.write("\n")
        print(json.dumps({k: result[k] for k in ("browser", "pages_checked", "interactive_steps", "all_clear", "console_or_page_errors")}, indent=1))
        return 0 if result["all_clear"] else 1
    finally:
        srv.terminate()


if __name__ == "__main__":
    sys.exit(main())
