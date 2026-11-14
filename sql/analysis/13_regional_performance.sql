-- title: Regional performance (customer macro-region)
-- question: How do revenue, order value, freight cost and service level differ across Brazil's regions?
-- technique: star join fact_orders -> dim_customer, ratio metrics computed from sums (not averages of ratios), share of total
-- insight: The Southeast produces 65.4% of revenue with the fastest delivery (10.7 days).
-- insight: North and Northeast customers spend more per order (BRL 182 and 165 vs 131) but pay freight equal to 22-23% of item value and wait about twice as long (20-23 days); the Northeast has the lowest on-time rate (87.2%) and review score (3.91).
SELECT
    c.region,
    count(DISTINCT o.customer_key)                                   AS customers,
    count(*)                                                         AS orders,
    round(sum(o.items_value), 0)                                     AS revenue_brl,
    round(100.0 * sum(o.items_value) / sum(sum(o.items_value)) OVER (), 1) AS revenue_pct,
    round(avg(o.items_value), 1)                                     AS aov_brl,
    round(100.0 * sum(o.freight_value) / sum(o.items_value), 1)      AS freight_to_revenue_pct,
    round(avg(o.delivery_days), 1)                                   AS avg_delivery_days,
    round(100.0 * avg(CASE WHEN o.is_on_time THEN 1 ELSE 0 END)
          FILTER (WHERE o.is_delivered), 1)                          AS on_time_pct,
    round(avg(o.review_score), 2)                                    AS avg_review
FROM fact_orders  AS o
JOIN dim_customer AS c ON o.customer_key = c.customer_key
JOIN dim_date     AS d ON o.purchase_date_key = d.date_key
WHERE o.is_valid_sale AND d.is_reporting_period
GROUP BY c.region
ORDER BY revenue_brl DESC;
