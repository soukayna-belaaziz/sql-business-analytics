-- title: Category performance and like-for-like growth
-- question: Which product categories drive revenue, which are growing, and which have satisfaction problems?
-- technique: item-level fact joined to dim_product and fact_orders, FILTER for Jan-Aug 2017 vs 2018 growth, share of total with window SUM, QUALIFY to keep the top 15
-- insight: The top 15 categories make 76% of revenue, led by health_beauty (9.3%) and watches_gifts (8.9%); baby (+264%), watches_gifts (+243%) and health_beauty (+211%) grow fastest like-for-like, while cool_stuff (+8.9%) and toys (+41.8%) lag the marketplace (+138%).
-- insight: office_furniture combines the lowest review (3.50) with the highest freight-to-price ratio (25%): bulky items are a satisfaction risk.
WITH items AS (
    SELECT
        p.category,
        f.order_id,
        f.price,
        f.freight_value,
        d.year,
        d.month,
        o.review_score
    FROM fact_order_items AS f
    JOIN dim_product      AS p ON f.product_key = p.product_key
    JOIN dim_date         AS d ON f.purchase_date_key = d.date_key
    JOIN fact_orders      AS o ON f.order_id = o.order_id
    WHERE f.is_valid_sale AND d.is_reporting_period
)
SELECT
    category,
    round(sum(price), 0)                                            AS revenue_brl,
    round(100.0 * sum(price) / sum(sum(price)) OVER (), 1)          AS revenue_pct,
    count(DISTINCT order_id)                                        AS orders,
    round(avg(price), 1)                                            AS avg_item_price,
    round(100.0 * sum(freight_value) / sum(price), 1)               AS freight_to_price_pct,
    round(avg(review_score), 2)                                     AS avg_review,
    round(100.0 * (sum(price) FILTER (WHERE year = 2018 AND month <= 8)
                 / sum(price) FILTER (WHERE year = 2017 AND month <= 8) - 1), 1) AS yoy_jan_aug_pct
FROM items
GROUP BY category
QUALIFY row_number() OVER (ORDER BY sum(price) DESC) <= 15
ORDER BY revenue_brl DESC;
