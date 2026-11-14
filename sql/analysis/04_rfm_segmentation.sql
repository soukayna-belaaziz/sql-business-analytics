-- title: RFM segmentation
-- question: Which customer segments exist by recency, frequency and monetary value, and how much revenue does each hold?
-- technique: per-customer aggregation, NTILE(5) quintiles for Recency and Monetary, rule-based Frequency score (97% of customers buy once, so frequency quintiles would be arbitrary ties), CASE segment rules
-- insight: About 97% of customers bought once in the period, so in practice the segmentation is driven by recency and spend.
-- insight: 'New high-value' (15.5% of customers) and 'At risk, high-value' (14.7%) together hold 58% of revenue; the at-risk group (last purchase about 13 months ago, avg BRL 278) is the natural target for a win-back campaign. Repeat buyers (segments 1-2) are 3% of customers and 5.6% of revenue.
WITH customer AS (
    SELECT
        o.customer_key,
        date_diff('day', CAST(max(o.purchase_ts) AS DATE), DATE '2018-09-01') AS recency_days,
        count(*)                AS frequency,
        sum(o.items_value)      AS monetary
    FROM fact_orders AS o
    JOIN dim_date    AS d ON o.purchase_date_key = d.date_key
    WHERE o.is_valid_sale AND d.is_reporting_period
    GROUP BY o.customer_key
), scored AS (
    SELECT
        *,
        NTILE(5) OVER (ORDER BY recency_days DESC, customer_key) AS r_score,  -- 5 = most recent
        NTILE(5) OVER (ORDER BY monetary ASC, customer_key)      AS m_score,  -- 5 = highest spend
        CASE WHEN frequency >= 3 THEN 5 WHEN frequency = 2 THEN 4 ELSE 1 END AS f_score
    FROM customer
), segmented AS (
    SELECT
        *,
        CASE
            WHEN f_score >= 4 AND r_score >= 4 THEN '1 Champions (repeat, recent)'
            WHEN f_score >= 4                  THEN '2 Loyal, lapsing (repeat, not recent)'
            WHEN r_score >= 4 AND m_score >= 4 THEN '3 New high-value'
            WHEN r_score >= 4                  THEN '4 New low-value'
            WHEN r_score = 3                   THEN '5 Needs attention'
            WHEN m_score >= 4                  THEN '6 At risk, high-value'
            ELSE                                    '7 Hibernating, low-value'
        END AS segment
    FROM scored
)
SELECT
    segment,
    count(*)                                                    AS customers,
    round(100.0 * count(*) / sum(count(*)) OVER (), 1)          AS customers_pct,
    round(avg(recency_days), 0)                                 AS avg_recency_days,
    round(avg(frequency), 2)                                    AS avg_orders,
    round(avg(monetary), 1)                                     AS avg_revenue_brl,
    round(100.0 * sum(monetary) / sum(sum(monetary)) OVER (), 1) AS revenue_pct
FROM segmented
GROUP BY segment
ORDER BY segment;
