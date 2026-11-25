"""Headless smoke test: build the site, serve it, run the sample in Chromium, check the output.

Usage: python demo/smoke_test.py [--url URL] [--screenshot PATH]
"""

from __future__ import annotations

import argparse
import functools
import http.server
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import build  # noqa: E402

# Substrings the tool's own printed summary must contain, and result tabs that must appear.
EXPECT_LOG = ["64 rows: 59 categorized, 5 uncategorized, 4 possible duplicates"]
EXPECT_TABS: list[str] = []


def serve(folder: Path) -> str:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(folder))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{httpd.server_port}/"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", help="test a deployed page instead of a local build")
    ap.add_argument("--screenshot", help="save a screenshot of the result")
    args = ap.parse_args()
    url = args.url or serve(build())
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(url)
        page.on("console", lambda m: m.type == "error" and errors.append(m.text))
        ready = "['ok', 'bad'].includes(document.querySelector('#status').dataset.kind)"
        page.wait_for_function(ready, timeout=180_000)
        if page.get_attribute("body", "data-ready") != "1":
            print(f"FAIL: runtime did not load: {page.inner_text('#status')} {errors}")
            return 1
        page.click("#run-sample")
        page.wait_for_function(
            "document.querySelector('#status').dataset.kind !== 'busy'", timeout=180_000
        )
        log = page.inner_text("#log")
        tabs = page.inner_text("#tabs")
        rows = page.locator("#table tbody tr").count()
        status = page.inner_text("#status")
        href = page.get_attribute("#download", "href") or ""
        print(f"status: {status}\nlog:\n{log}\ntabs: {tabs}\nrows shown: {rows}")
        if args.screenshot:
            page.locator("main").screenshot(path=args.screenshot)
        browser.close()
    problems = [f"log missing {s!r}" for s in EXPECT_LOG if s not in log]
    problems += [f"tab missing {t!r}" for t in EXPECT_TABS if t not in tabs]
    if rows == 0:
        problems.append("result table is empty")
    if not href.startswith("blob:"):
        problems.append("no download link")
    if status != "Done.":
        problems.append(f"status is {status!r}")
    problems += [f"page error: {e}" for e in errors]
    for p_ in problems:
        print(f"FAIL: {p_}")
    print("PASS" if not problems else "FAILED")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
