-- title: Year-to-date KPI comparison (Jan-Aug 2018 vs Jan-Aug 2017)
-- question: What do the headline KPIs look like this year versus the same period last year?
-- technique: conditional aggregation (FILTER), like-for-like period comparison, UNPIVOT-style layout with a VALUES table
-- insight: Jan-Aug 2018 revenue is +138% on the same period of 2017, almost entirely volume-driven (orders +137%, AOV flat at about BRL 137).
-- insight: Service quality did not keep pace: on-time delivery fell from 96.5% to 92.3% and the average review from 4.18 to 4.11. Repeat orders are only 3.5% of orders.
WITH ytd AS (
    SELECT
        d.year,
        count(*)                                        AS orders,
        count(DISTINCT o.customer_key)                  AS customers,
        sum(o.items_value)                              AS revenue,
        sum(o.freight_value)                            AS freight,
        avg(o.items_value)                              AS aov,
        avg(o.items_count)                              AS items_per_order,
        avg(CASE WHEN o.is_on_time THEN 1.0 ELSE 0.0 END)
            FILTER (WHERE o.is_delivered)               AS on_time_rate,
        avg(o.delivery_days) FILTER (WHERE o.is_delivered) AS delivery_days,
        avg(o.review_score)                             AS avg_review,
        avg(CASE WHEN o.customer_order_seq > 1 THEN 1.0 ELSE 0.0 END) AS repeat_order_share
    FROM fact_orders AS o
    JOIN dim_date    AS d ON o.purchase_date_key = d.date_key
    WHERE o.is_valid_sale
      AND d.month BETWEEN 1 AND 8
      AND d.year IN (2017, 2018)
    GROUP BY d.year
), pivoted AS (
    SELECT
        k.kpi, k.sort_order,
        max(CASE WHEN y.year = 2017 THEN k.val END) AS v2017,
        max(CASE WHEN y.year = 2018 THEN k.val END) AS v2018
    FROM ytd AS y,
    LATERAL (VALUES
        (1, 'Orders',                    CAST(y.orders AS DOUBLE)),
        (2, 'Active customers',          CAST(y.customers AS DOUBLE)),
        (3, 'Revenue (BRL)',             CAST(y.revenue AS DOUBLE)),
        (4, 'Freight billed (BRL)',      CAST(y.freight AS DOUBLE)),
        (5, 'Average order value (BRL)', CAST(y.aov AS DOUBLE)),
        (6, 'Items per order',           y.items_per_order),
        (7, 'On-time delivery %',        100 * y.on_time_rate),
        (8, 'Avg delivery days',         y.delivery_days),
        (9, 'Avg review score',          y.avg_review),
        (10, 'Repeat-order share %',     100 * y.repeat_order_share)
    ) AS k(sort_order, kpi, val)
    GROUP BY k.kpi, k.sort_order
)
SELECT
    kpi,
    round(v2017, 2)                       AS jan_aug_2017,
    round(v2018, 2)                       AS jan_aug_2018,
    round(100 * (v2018 / v2017 - 1), 1)   AS change_pct
FROM pivoted
ORDER BY sort_order;
