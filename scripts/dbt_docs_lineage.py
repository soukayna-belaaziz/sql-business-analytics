"""Generate the dbt docs site and screenshot the full lineage graph.

Usage:  python scripts/dbt_docs_lineage.py
Output: olist_dbt/target/static_index.html (self-contained docs site, git-ignored)
        reports/figures/dbt_lineage.png
Needs the database built by `python -m src.pipeline` (the catalog reads it).
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import DB_PATH, DBT_TARGET_DIR, FIGURES_DIR, RAW_DIR  # noqa: E402
from src.dbt_runner import run_dbt  # noqa: E402

OUT = FIGURES_DIR / "dbt_lineage.png"


def main() -> None:
    run_dbt(["docs", "generate", "--static"], RAW_DIR, DB_PATH)
    site = DBT_TARGET_DIR / "static_index.html"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1800, "height": 1000})
        page.goto(site.as_uri() + "#!/overview?g_v=1", wait_until="load")
        page.wait_for_selector("canvas, #cy", timeout=60_000)
        time.sleep(5)  # let the cytoscape layout settle
        OUT.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(OUT))
        browser.close()
    print(f"Saved {OUT} (docs site: {site})")


if __name__ == "__main__":
    main()
