-- title: Seller late-shipping scorecard
-- question: Do sellers who hand parcels to the carrier after the agreed shipping limit get worse reviews?
-- technique: seller-level KPIs from the item fact, HAVING for a minimum volume, CASE banding of late-shipping rate, weighted averages
-- insight: Among sellers with 50+ orders, those handing parcels to the carrier late more than 20% of the time have a weighted review of 3.78 and 21.9% negative reviews, versus 4.15 and 13.3% for sellers below 5% late.
-- insight: These 62 sellers still generate 11.8% of the revenue of this group, so enforcing shipping SLAs is a lever with measurable satisfaction impact.
WITH seller AS (
    SELECT
        f.seller_key,
        count(DISTINCT f.order_id)                                   AS orders,
        sum(f.price)                                                 AS revenue,
        avg(CASE WHEN f.is_shipped_late THEN 1.0 ELSE 0.0 END)       AS late_ship_rate,
        avg(o.review_score)                                          AS avg_review,
        avg(CASE WHEN o.review_score <= 2 THEN 1.0 ELSE 0.0 END)
            FILTER (WHERE o.review_score IS NOT NULL)                AS negative_rate
    FROM fact_order_items AS f
    JOIN fact_orders      AS o ON f.order_id = o.order_id
    JOIN dim_date         AS d ON f.purchase_date_key = d.date_key
    WHERE f.is_valid_sale AND d.is_reporting_period
      AND f.is_shipped_late IS NOT NULL
    GROUP BY f.seller_key
    HAVING count(DISTINCT f.order_id) >= 50
)
SELECT
    CASE
        WHEN late_ship_rate < 0.05 THEN '1 < 5% late'
        WHEN late_ship_rate < 0.10 THEN '2 5-10% late'
        WHEN late_ship_rate < 0.20 THEN '3 10-20% late'
        ELSE                            '4 20%+ late'
    END                                                          AS late_shipping_band,
    count(*)                                                     AS sellers,
    CAST(sum(orders) AS BIGINT)                                  AS orders,
    round(100.0 * sum(revenue) / sum(sum(revenue)) OVER (), 1)   AS revenue_pct,
    round(100.0 * sum(late_ship_rate * orders) / sum(orders), 1) AS late_ship_pct,
    round(sum(avg_review * orders) / sum(orders), 2)             AS avg_review_weighted,
    round(100.0 * sum(negative_rate * orders) / sum(orders), 1)  AS negative_review_pct
FROM seller
GROUP BY 1
ORDER BY 1;
