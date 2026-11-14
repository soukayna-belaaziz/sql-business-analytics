-- =============================================================================
-- Data-quality checks on the mart.
-- Every check returns ONE row: (check_name, category, severity, failing_rows).
--   severity = 'error' -> must be 0, the pipeline and pytest fail otherwise
--   severity = 'warn'  -> known source issue, reported and monitored, not fatal
-- =============================================================================

-- 1. Row-count reconciliation staging -> mart (no silent row loss in joins)
SELECT 'orders: stg vs fact_orders' AS check_name, 'row_count' AS category, 'error' AS severity,
       abs((SELECT count(*) FROM stg_orders) - (SELECT count(*) FROM fact_orders)) AS failing_rows
UNION ALL
SELECT 'order items: stg vs fact_order_items', 'row_count', 'error',
       abs((SELECT count(*) FROM stg_order_items) - (SELECT count(*) FROM fact_order_items))
UNION ALL
SELECT 'payments: stg vs fact_payments', 'row_count', 'error',
       abs((SELECT count(*) FROM stg_order_payments) - (SELECT count(*) FROM fact_payments))
UNION ALL
SELECT 'revenue: stg items vs fact_order_items (BRL cents)', 'row_count', 'error',
       CAST(abs((SELECT coalesce(sum(price), 0) FROM stg_order_items)
              - (SELECT coalesce(sum(price), 0) FROM fact_order_items)) * 100 AS BIGINT)

-- 2. Primary-key uniqueness
UNION ALL
SELECT 'pk unique: fact_orders.order_id', 'duplicates', 'error',
       count(*) - count(DISTINCT order_id) FROM fact_orders
UNION ALL
SELECT 'pk unique: fact_order_items(order_id, order_item_id)', 'duplicates', 'error',
       count(*) - count(DISTINCT (order_id, order_item_id)) FROM fact_order_items
UNION ALL
SELECT 'pk unique: fact_payments(order_id, payment_sequential)', 'duplicates', 'error',
       count(*) - count(DISTINCT (order_id, payment_sequential)) FROM fact_payments
UNION ALL
SELECT 'pk unique: dim_customer.customer_key', 'duplicates', 'error',
       count(*) - count(DISTINCT customer_key) FROM dim_customer
UNION ALL
SELECT 'pk unique: dim_product.product_key', 'duplicates', 'error',
       count(*) - count(DISTINCT product_key) FROM dim_product
UNION ALL
SELECT 'pk unique: dim_seller.seller_key', 'duplicates', 'error',
       count(*) - count(DISTINCT seller_key) FROM dim_seller
UNION ALL
SELECT 'pk unique: dim_date.date_key', 'duplicates', 'error',
       count(*) - count(DISTINCT date_key) FROM dim_date

-- 3. Not-null on keys and mandatory measures
UNION ALL
SELECT 'not null: fact_orders keys/timestamps', 'nulls', 'error',
       count(*) FILTER (WHERE order_id IS NULL OR customer_key IS NULL
                           OR purchase_ts IS NULL OR purchase_date_key IS NULL)
FROM fact_orders
UNION ALL
SELECT 'not null: fact_order_items keys/price', 'nulls', 'error',
       count(*) FILTER (WHERE product_key IS NULL OR seller_key IS NULL
                           OR price IS NULL OR freight_value IS NULL)
FROM fact_order_items

-- 4. Referential integrity fact -> dimension
UNION ALL
SELECT 'fk: fact_orders.customer_key -> dim_customer', 'referential_integrity', 'error',
       count(*) FROM fact_orders f
       WHERE NOT EXISTS (SELECT 1 FROM dim_customer d WHERE d.customer_key = f.customer_key)
UNION ALL
SELECT 'fk: fact_orders.purchase_date_key -> dim_date', 'referential_integrity', 'error',
       count(*) FROM fact_orders f
       WHERE NOT EXISTS (SELECT 1 FROM dim_date d WHERE d.date_key = f.purchase_date_key)
UNION ALL
SELECT 'fk: fact_order_items.product_key -> dim_product', 'referential_integrity', 'error',
       count(*) FROM fact_order_items f
       WHERE NOT EXISTS (SELECT 1 FROM dim_product d WHERE d.product_key = f.product_key)
UNION ALL
SELECT 'fk: fact_order_items.seller_key -> dim_seller', 'referential_integrity', 'error',
       count(*) FROM fact_order_items f
       WHERE NOT EXISTS (SELECT 1 FROM dim_seller d WHERE d.seller_key = f.seller_key)
UNION ALL
SELECT 'fk: stg_order_items.order_id -> stg_orders (orphan lines)', 'referential_integrity', 'error',
       count(*) FROM stg_order_items i
       WHERE NOT EXISTS (SELECT 1 FROM stg_orders o WHERE o.order_id = i.order_id)

-- 5. Business-rule / range checks
UNION ALL
SELECT 'range: item price > 0', 'validity', 'error',
       count(*) FILTER (WHERE price <= 0) FROM fact_order_items
UNION ALL
SELECT 'range: freight_value >= 0', 'validity', 'error',
       count(*) FILTER (WHERE freight_value < 0) FROM fact_order_items
UNION ALL
SELECT 'range: payment_value >= 0', 'validity', 'error',
       count(*) FILTER (WHERE payment_value < 0) FROM fact_payments
UNION ALL
SELECT 'range: review_score in 1..5', 'validity', 'error',
       count(*) FILTER (WHERE review_score NOT BETWEEN 1 AND 5) FROM fact_orders
UNION ALL
SELECT 'domain: order_status in known list', 'validity', 'error',
       count(*) FILTER (WHERE order_status NOT IN
           ('created', 'approved', 'invoiced', 'processing', 'shipped',
            'delivered', 'canceled', 'unavailable'))
FROM fact_orders

-- 6. Known source issues (warnings, documented in the README)
UNION ALL
SELECT 'warn: orders without any item line', 'completeness', 'warn',
       count(*) FILTER (WHERE items_count = 0) FROM fact_orders
UNION ALL
SELECT 'warn: delivered orders without delivery timestamp', 'completeness', 'warn',
       count(*) FILTER (WHERE order_status = 'delivered' AND delivered_customer_ts IS NULL)
FROM fact_orders
UNION ALL
SELECT 'warn: delivered to customer before purchase', 'validity', 'warn',
       count(*) FILTER (WHERE delivered_customer_ts < purchase_ts) FROM fact_orders
UNION ALL
SELECT 'warn: handed to carrier before purchase', 'validity', 'warn',
       count(*) FILTER (WHERE delivered_carrier_ts < purchase_ts) FROM fact_orders
UNION ALL
SELECT 'warn: payments differ from items+freight by > 1 BRL', 'consistency', 'warn',
       count(*) FILTER (WHERE items_count > 0 AND payment_value > 0
                          AND abs(payment_value - items_value - freight_value) > 1)
FROM fact_orders
UNION ALL
SELECT 'warn: products without category', 'completeness', 'warn',
       count(*) FILTER (WHERE category = 'unknown') FROM dim_product
UNION ALL
SELECT 'warn: orders with >1 review in source (deduplicated)', 'duplicates', 'warn',
       (SELECT count(*) FROM (SELECT order_id FROM stg_order_reviews
                              GROUP BY order_id HAVING count(*) > 1))
UNION ALL
SELECT 'warn: valid-sale orders without a review', 'completeness', 'warn',
       count(*) FILTER (WHERE is_valid_sale AND review_score IS NULL) FROM fact_orders
