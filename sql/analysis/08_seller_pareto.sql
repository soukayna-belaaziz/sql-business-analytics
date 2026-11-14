-- title: Seller revenue concentration (Pareto / 80-20)
-- question: How concentrated is revenue across sellers - what share of sellers generates 80% of revenue?
-- technique: per-seller revenue, NTILE(10) deciles, running SUM() OVER for cumulative share
-- insight: Revenue is strongly concentrated: the top 10% of sellers (303) generate 67.4% of revenue and the top 20% generate 82.5% - a textbook 80/20 pattern; the bottom half of sellers contributes 3.3%.
-- insight: A key-account programme covering about 600 sellers would cover more than 80% of revenue.
WITH seller_revenue AS (
    SELECT
        f.seller_key,
        sum(f.price)                AS revenue,
        count(DISTINCT f.order_id)  AS orders
    FROM fact_order_items AS f
    JOIN dim_date         AS d ON f.purchase_date_key = d.date_key
    WHERE f.is_valid_sale AND d.is_reporting_period
    GROUP BY f.seller_key
), ranked AS (
    SELECT
        *,
        NTILE(10) OVER (ORDER BY revenue DESC, seller_key) AS decile
    FROM seller_revenue
), by_decile AS (
    SELECT
        decile,
        count(*)            AS sellers,
        sum(revenue)        AS revenue,
        sum(orders)         AS orders,
        min(revenue)        AS min_seller_revenue
    FROM ranked
    GROUP BY decile
)
SELECT
    decile                                                             AS seller_decile,
    sellers,
    round(revenue, 0)                                                  AS revenue_brl,
    round(100.0 * revenue / sum(revenue) OVER (), 1)                   AS revenue_pct,
    round(100.0 * sum(revenue) OVER (ORDER BY decile) / sum(revenue) OVER (), 1) AS cumulative_revenue_pct,
    round(min_seller_revenue, 0)                                       AS min_seller_revenue_brl
FROM by_decile
ORDER BY decile;
