"""Shared fixtures: build the full ETL on a tiny hand-made dataset.

The fixture (tests/fixtures/*.csv) has 5 orders from 4 real customers and
contains on purpose: one customer with two customer_ids, a canceled order,
a duplicated review, a product without category, a category missing from the
translation file, a 0-instalment payment and untrimmed/lower-case text.
Expected values in the tests are computed by hand from those CSVs.
"""
from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from src.build_db import build_database

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture()
def con() -> duckdb.DuckDBPyConnection:
    """Fresh in-memory database built from the fixture CSVs."""
    connection = build_database(FIXTURE_DIR, ":memory:")
    yield connection
    connection.close()
