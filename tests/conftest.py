"""Shared fixtures: build the full dbt project on a tiny hand-made dataset.

The fixture (tests/fixtures/*.csv) has 5 orders from 4 real customers and
contains on purpose: one customer with two customer_ids, a canceled order,
a duplicated review, a product without category, a category missing from the
translation file, a 0-instalment payment and untrimmed/lower-case text.
Expected values in the tests are computed by hand from those CSVs.

``dbt build`` runs once per test session (about 10 s); each test then gets
its own copy of the database file, so tests that inject defects stay isolated.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import duckdb
import pytest

from src.build_db import build_database

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def built_db(tmp_path_factory) -> Path:
    """Path of a DuckDB file built by ``dbt build`` from the fixture CSVs."""
    work = tmp_path_factory.mktemp("dbt")
    db_path = work / "fixture.duckdb"
    build_database(FIXTURE_DIR, db_path, target_dir=work / "target").close()
    return db_path


@pytest.fixture()
def db_copy(built_db: Path, tmp_path: Path) -> Path:
    """A private copy of the fixture database for one test."""
    path = tmp_path / "copy.duckdb"
    shutil.copy(built_db, path)
    return path


@pytest.fixture()
def con(db_copy: Path) -> duckdb.DuckDBPyConnection:
    """Connection to a fresh copy of the fixture database."""
    connection = duckdb.connect(str(db_copy))
    yield connection
    connection.close()
