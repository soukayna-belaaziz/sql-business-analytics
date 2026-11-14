"""Start the Streamlit app headless and save a full-page screenshot.

Usage:  python scripts/screenshot_dashboard.py
Output: reports/figures/dashboard_screenshot.png
"""
from __future__ import annotations

import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "figures" / "dashboard_screenshot.png"
PORT = 8599
URL = f"http://localhost:{PORT}"


def wait_for_server(url: str, timeout: float = 60.0) -> None:
    """Poll the Streamlit health endpoint until it answers."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{url}/_stcore/health", timeout=2) as r:
                if r.status == 200:
                    return
        except OSError:
            time.sleep(1)
    raise TimeoutError("Streamlit did not start")


def main() -> None:
    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "app.py", "--server.headless", "true",
         "--server.port", str(PORT), "--browser.gatherUsageStats", "false",
         "--theme.base", "light", "--client.toolbarMode", "viewer"],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        wait_for_server(URL)
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 1240})
            page.goto(URL, wait_until="networkidle")
            page.wait_for_selector("text=Monthly revenue", timeout=60_000)
            page.wait_for_selector("canvas, svg.marks", timeout=60_000)
            time.sleep(4)  # let Vega finish rendering all charts
            OUT.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(OUT), full_page=True)
            browser.close()
        print(f"Saved {OUT}")
    finally:
        proc.terminate()
        proc.wait(timeout=20)


if __name__ == "__main__":
    main()
