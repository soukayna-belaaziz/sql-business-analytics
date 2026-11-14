"""Download the Olist Brazilian e-commerce public dataset from GitHub.

Source: https://github.com/olist/work-at-olist-data (folder ``datasets/``).
The same data is published by Olist on Kaggle as "Brazilian E-Commerce Public
Dataset by Olist" under CC BY-NC-SA 4.0. Files are saved to ``data/raw/`` and
are not committed (about 64 MB in total). The geolocation table (61 MB) is not
needed by this project and is skipped.

Usage:
    python data/download_data.py
"""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

BASE_URL = "https://raw.githubusercontent.com/olist/work-at-olist-data/master/datasets"
FILES: tuple[str, ...] = (
    "olist_customers_dataset.csv",
    "olist_orders_dataset.csv",
    "olist_order_items_dataset.csv",
    "olist_order_payments_dataset.csv",
    "olist_order_reviews_dataset.csv",
    "olist_products_dataset.csv",
    "olist_sellers_dataset.csv",
    "product_category_name_translation.csv",
)
RAW_DIR = Path(__file__).resolve().parent / "raw"


def download(file_name: str, dest_dir: Path = RAW_DIR, force: bool = False) -> Path:
    """Download one CSV into ``dest_dir`` unless it already exists."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / file_name
    if target.exists() and target.stat().st_size > 0 and not force:
        print(f"[skip] {file_name} already present")
        return target
    url = f"{BASE_URL}/{file_name}"
    print(f"[get ] {url}")
    tmp = target.with_suffix(".part")
    urllib.request.urlretrieve(url, tmp)
    tmp.replace(target)
    return target


def main() -> int:
    force = "--force" in sys.argv
    for name in FILES:
        download(name, force=force)
    print(f"Done. Files in {RAW_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
