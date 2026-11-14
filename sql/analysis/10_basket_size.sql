-- title: Basket size and composition
-- question: How often do customers buy more than one item, product, seller or category in one order, and what is the order value by basket size?
-- technique: order-level aggregation of item lines (COUNT DISTINCT), CASE bucketing, share with window SUM
-- insight: 90.1% of orders contain a single item; multi-item orders are 9.9% of orders and 14.7% of revenue.
-- insight: Even 2-item baskets mostly repeat the same product (only 33.5% contain two different products and 7.8% two categories) - cross-selling is a largely untapped lever.
WITH baskets AS (
    SELECT
        f.order_id,
        count(*)                          AS items,
        count(DISTINCT f.product_key)     AS distinct_products,
        count(DISTINCT f.seller_key)      AS distinct_sellers,
        count(DISTINCT p.category)        AS distinct_categories,
        sum(f.price)                      AS order_value
    FROM fact_order_items AS f
    JOIN dim_product      AS p ON f.product_key = p.product_key
    JOIN dim_date         AS d ON f.purchase_date_key = d.date_key
    WHERE f.is_valid_sale AND d.is_reporting_period
    GROUP BY f.order_id
)
SELECT
    CASE WHEN items >= 4 THEN '4+' ELSE CAST(items AS VARCHAR) END    AS items_in_order,
    count(*)                                                         AS orders,
    round(100.0 * count(*) / sum(count(*)) OVER (), 2)               AS orders_pct,
    round(100.0 * sum(order_value) / sum(sum(order_value)) OVER (), 1) AS revenue_pct,
    round(avg(order_value), 1)                                       AS avg_order_value_brl,
    round(100.0 * avg(CASE WHEN distinct_products > 1 THEN 1 ELSE 0 END), 1)   AS multi_product_pct,
    round(100.0 * avg(CASE WHEN distinct_sellers > 1 THEN 1 ELSE 0 END), 1)    AS multi_seller_pct,
    round(100.0 * avg(CASE WHEN distinct_categories > 1 THEN 1 ELSE 0 END), 1) AS multi_category_pct
FROM baskets
GROUP BY 1
ORDER BY 1;
