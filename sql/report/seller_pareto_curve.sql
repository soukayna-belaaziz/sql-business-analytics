-- Seller-level cumulative revenue curve for the Pareto chart.
WITH s AS (
    SELECT f.seller_key, sum(f.price) AS revenue
    FROM fact_order_items AS f
    JOIN dim_date AS d ON f.purchase_date_key = d.date_key
    WHERE f.is_valid_sale AND d.is_reporting_period
    GROUP BY f.seller_key
)
SELECT
    row_number() OVER (ORDER BY revenue DESC, seller_key) * 100.0 / count(*) OVER () AS cum_sellers_pct,
    sum(revenue) OVER (ORDER BY revenue DESC, seller_key) * 100.0 / sum(revenue) OVER () AS cum_revenue_pct
FROM s
ORDER BY cum_sellers_pct;
