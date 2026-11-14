"""dbt tests: the clean fixture passes, known issues warn, injected defects fail."""
from __future__ import annotations

import duckdb
import pytest

from src.quality import DataQualityError, assert_no_errors, collect_test_results, run_tests
from tests.conftest import FIXTURE_DIR


def status_of(results, name: str) -> tuple[str, int]:
    row = results.loc[results["check_name"] == name].iloc[0]
    return row["status"], int(row["failing_rows"])


@pytest.fixture(scope="module")
def build_results(built_db):
    """Test results recorded by the session's `dbt build` on the fixture."""
    return collect_test_results(built_db.parent / "target")


def test_fixture_build_has_no_error_level_failures(build_results):
    assert len(build_results) >= 40
    assert (build_results["status"] != "FAIL").all(), build_results[build_results.status == "FAIL"]
    assert_no_errors(build_results)


def test_known_source_issues_are_reported_as_warnings(build_results):
    assert status_of(build_results, "warn_products_without_category") == ("WARN", 1)
    assert status_of(build_results,
                     "warn_stg_order_reviews_more_than_one_review_per_order") == ("WARN", 1)
    assert set(build_results.loc[build_results.status == "WARN", "severity"]) == {"warn"}


def test_injected_defects_are_caught(db_copy, tmp_path):
    """Duplicate PK, orphan FK, lost rows and a negative price in one dbt test run."""
    con = duckdb.connect(str(db_copy))
    con.execute("INSERT INTO fact_orders SELECT * FROM fact_orders WHERE order_id = 'o1'")
    con.execute("UPDATE fact_order_items SET product_key = 'ghost' WHERE order_id = 'o3'")
    con.execute("DELETE FROM fact_payments WHERE order_id = 'o4'")
    con.execute("UPDATE fact_order_items SET price = -1 WHERE order_id = 'o1' AND order_item_id = 1")
    con.close()

    results = run_tests(db_copy, FIXTURE_DIR, tmp_path / "target")
    assert status_of(results, "unique_fact_orders_order_id") == ("FAIL", 1)
    assert status_of(results, "rowcount_stg_orders_vs_fact_orders") == ("FAIL", 1)
    assert status_of(results, "fk_fact_order_items_product_key__dim_product") == ("FAIL", 1)
    assert status_of(results, "rowcount_stg_order_payments_vs_fact_payments") == ("FAIL", 1)
    assert status_of(results, "range_item_price_positive") == ("FAIL", 1)
    with pytest.raises(DataQualityError):
        assert_no_errors(results)
