-- title: Delivery SLA vs customer review score
-- question: How does delivering early or late against the promised date affect the review score?
-- technique: CASE bucketing of delay_days, share of 1-2 star reviews, window function for the share of orders per bucket
-- insight: Review scores follow the delivery promise: orders delivered early average 4.2-4.3 stars with about 9% negative (1-2 star) reviews; 4-7 days late drops to 2.10 stars with 68% negative, and beyond a week late about 80% are negative.
-- insight: Late orders are only 6.7% of reviewed deliveries but account for 32.6% of all negative reviews (sum of the last column over the four late buckets).
WITH delivered AS (
    SELECT
        o.delay_days,
        o.review_score,
        CASE
            WHEN o.delay_days <= -15 THEN '1 early 15+ days'
            WHEN o.delay_days <= -8  THEN '2 early 8-14 days'
            WHEN o.delay_days <= -1  THEN '3 early 1-7 days'
            WHEN o.delay_days = 0    THEN '4 on the estimated day'
            WHEN o.delay_days <= 3   THEN '5 late 1-3 days'
            WHEN o.delay_days <= 7   THEN '6 late 4-7 days'
            WHEN o.delay_days <= 14  THEN '7 late 8-14 days'
            ELSE                          '8 late 15+ days'
        END AS delay_bucket
    FROM fact_orders AS o
    JOIN dim_date    AS d ON o.purchase_date_key = d.date_key
    WHERE o.is_delivered
      AND o.review_score IS NOT NULL
      AND d.is_reporting_period
)
SELECT
    delay_bucket,
    count(*)                                                       AS orders,
    round(100.0 * count(*) / sum(count(*)) OVER (), 1)             AS orders_pct,
    round(avg(review_score), 2)                                    AS avg_review,
    round(100.0 * avg(CASE WHEN review_score <= 2 THEN 1 ELSE 0 END), 1) AS negative_review_pct,
    round(100.0 * avg(CASE WHEN review_score = 5 THEN 1 ELSE 0 END), 1)  AS five_star_pct,
    -- share of ALL negative reviews that fall in this bucket
    round(100.0 * count(*) FILTER (WHERE review_score <= 2)
          / sum(count(*) FILTER (WHERE review_score <= 2)) OVER (), 1)   AS share_of_all_negative_pct
FROM delivered
GROUP BY delay_bucket
ORDER BY delay_bucket;
