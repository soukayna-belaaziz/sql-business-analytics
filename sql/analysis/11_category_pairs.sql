-- title: Cross-category basket pairs (market-basket support and lift)
-- question: Which categories are bought together in the same order, and is the association stronger than chance?
-- note: lift = P(A and B) / (P(A) * P(B)); lift < 1 means the pair co-occurs less often than if purchases were independent
-- technique: self-join of distinct (order, category) pairs with a < b to avoid duplicates, support / confidence / lift computed in SQL
-- insight: Cross-category co-purchases are rare: the most frequent pair (bed_bath_table + furniture_decor) appears in 68 orders, 0.07% of all orders, and almost every pair has lift below 1 because about 99% of orders are single-category.
-- insight: Only bed_bath_table + home_confort (lift 1.11) co-occurs more often than chance; recommendations should start from within-category complements.
WITH order_category AS (
    SELECT DISTINCT f.order_id, p.category
    FROM fact_order_items AS f
    JOIN dim_product      AS p ON f.product_key = p.product_key
    JOIN dim_date         AS d ON f.purchase_date_key = d.date_key
    WHERE f.is_valid_sale AND d.is_reporting_period AND p.category <> 'unknown'
), n AS (
    SELECT count(DISTINCT order_id) AS total_orders FROM order_category
), cat AS (
    SELECT category, count(*) AS orders FROM order_category GROUP BY category
), pairs AS (
    SELECT a.category AS category_a, b.category AS category_b, count(*) AS orders_together
    FROM order_category AS a
    JOIN order_category AS b ON a.order_id = b.order_id AND a.category < b.category
    GROUP BY 1, 2
)
SELECT
    p.category_a,
    p.category_b,
    p.orders_together,
    round(100.0 * p.orders_together / n.total_orders, 3)                     AS support_pct,
    round(100.0 * p.orders_together / ca.orders, 2)                          AS confidence_a_to_b_pct,
    round(p.orders_together * n.total_orders / (ca.orders * cb.orders * 1.0), 2) AS lift
FROM pairs AS p
CROSS JOIN n
JOIN cat AS ca ON ca.category = p.category_a
JOIN cat AS cb ON cb.category = p.category_b
WHERE p.orders_together >= 10          -- minimum support: avoid lift on tiny counts
ORDER BY p.orders_together DESC, p.category_a, p.category_b
LIMIT 10;
