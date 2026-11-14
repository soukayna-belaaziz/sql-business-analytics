"""ETL tests: row counts, cleaning rules and mart definitions."""
from __future__ import annotations


def scalar(con, sql: str):
    return con.execute(sql).fetchone()[0]


def test_mart_row_counts(con):
    assert scalar(con, "SELECT count(*) FROM fact_orders") == 5
    assert scalar(con, "SELECT count(*) FROM fact_order_items") == 6
    assert scalar(con, "SELECT count(*) FROM fact_payments") == 6
    # c1 and c2 are the same person (u1) -> 4 customers in the dimension
    assert scalar(con, "SELECT count(*) FROM dim_customer") == 4
    assert scalar(con, "SELECT count(*) FROM dim_product") == 3
    assert scalar(con, "SELECT count(*) FROM dim_seller") == 2


def test_canceled_order_is_not_a_valid_sale(con):
    assert scalar(con, "SELECT is_valid_sale FROM fact_orders WHERE order_id = 'o5'") is False
    assert scalar(con, "SELECT count(*) FROM fact_orders WHERE is_valid_sale") == 4


def test_customer_order_sequence_uses_unique_id(con):
    seq = dict(con.execute(
        "SELECT order_id, customer_order_seq FROM fact_orders WHERE customer_key = 'u1'").fetchall())
    assert seq == {"o1": 1, "o2": 2}
    row = con.execute("SELECT lifetime_orders, lifetime_revenue, cohort_month "
                      "FROM dim_customer WHERE customer_key = 'u1'").fetchone()
    assert row[0] == 2 and float(row[1]) == 230.0 and row[2] == "2017-01"


def test_customer_with_only_canceled_orders_has_no_cohort(con):
    row = con.execute("SELECT lifetime_orders, cohort_month FROM dim_customer "
                      "WHERE customer_key = 'u4'").fetchone()
    assert row == (0, None)


def test_text_standardisation(con):
    row = con.execute("SELECT city, state, zip_prefix FROM dim_customer "
                      "WHERE customer_key = 'u1'").fetchone()
    assert row == ("sao paulo", "SP", "01001")
    assert scalar(con, "SELECT region FROM dim_customer WHERE customer_key = 'u2'") == "Northeast"


def test_review_deduplication_keeps_latest(con):
    assert scalar(con, "SELECT review_score FROM fact_orders WHERE order_id = 'o2'") == 1


def test_category_translation_and_unknown(con):
    cats = dict(con.execute("SELECT product_key, category FROM dim_product").fetchall())
    assert cats == {"p1": "health_beauty", "p2": "unknown", "p3": "pc_gamer"}


def test_delivery_metrics(con):
    rows = {r[0]: r[1:] for r in con.execute(
        "SELECT order_id, delay_days, is_on_time, is_delivered FROM fact_orders").fetchall()}
    assert rows["o1"] == (-5, True, True)
    assert rows["o2"] == (5, False, True)
    assert rows["o4"] == (None, None, False)


def test_late_shipping_flag(con):
    late = dict(con.execute("SELECT order_id, is_shipped_late FROM fact_order_items "
                            "WHERE order_item_id = 1").fetchall())
    assert late["o2"] is True      # handed to carrier 02-09, limit 02-08
    assert late["o4"] is False
    assert late["o5"] is None      # never shipped


def test_zero_installments_cleaned_to_one(con):
    assert scalar(con, "SELECT payment_installments FROM fact_payments WHERE order_id = 'o5'") == 1


def test_order_totals(con):
    row = con.execute("SELECT items_count, items_value, freight_value, payment_value, "
                      "main_payment_type FROM fact_orders WHERE order_id = 'o3'").fetchone()
    assert row[0] == 1
    assert float(row[1]) == 200.0 and float(row[2]) == 20.0 and float(row[3]) == 220.0
    assert row[4] == "credit_card"
