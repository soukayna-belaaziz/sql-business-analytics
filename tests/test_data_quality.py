"""Data-quality checks: clean fixture passes, injected defects are caught."""
from __future__ import annotations

import pytest

from src.quality import DataQualityError, assert_no_errors, run_checks


def status_of(results, name: str) -> tuple[str, int]:
    row = results.loc[results["check_name"] == name].iloc[0]
    return row["status"], int(row["failing_rows"])


def test_fixture_has_no_error_level_failures(con):
    results = run_checks(con)
    assert (results["status"] != "FAIL").all(), results[results["status"] == "FAIL"]
    assert_no_errors(results)


def test_known_source_issues_are_reported_as_warnings(con):
    results = run_checks(con)
    assert status_of(results, "warn: products without category") == ("WARN", 1)
    assert status_of(results, "warn: orders with >1 review in source (deduplicated)") == ("WARN", 1)


def test_duplicate_primary_key_is_detected(con):
    con.execute("INSERT INTO fact_orders SELECT * FROM fact_orders WHERE order_id = 'o1'")
    results = run_checks(con)
    assert status_of(results, "pk unique: fact_orders.order_id") == ("FAIL", 1)
    with pytest.raises(DataQualityError):
        assert_no_errors(results)


def test_orphan_foreign_key_is_detected(con):
    con.execute("UPDATE fact_order_items SET product_key = 'ghost' WHERE order_id = 'o3'")
    results = run_checks(con)
    assert status_of(results, "fk: fact_order_items.product_key -> dim_product") == ("FAIL", 1)


def test_row_loss_is_detected(con):
    con.execute("DELETE FROM fact_payments WHERE order_id = 'o4'")
    results = run_checks(con)
    assert status_of(results, "payments: stg vs fact_payments") == ("FAIL", 1)


def test_negative_price_is_detected(con):
    con.execute("UPDATE fact_order_items SET price = -1 WHERE order_id = 'o1' AND order_item_id = 1")
    results = run_checks(con)
    assert status_of(results, "range: item price > 0")[0] == "FAIL"
