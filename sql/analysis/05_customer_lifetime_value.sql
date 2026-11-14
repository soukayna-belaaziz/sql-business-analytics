-- title: 12-month customer value by acquisition cohort
-- question: How much revenue does a newly acquired customer generate in their first 12 months, and how much of it comes from repeat purchases?
-- technique: cohort-based historical CLV with a fixed 12-month observation window (only cohorts with a full window: Jan-Aug 2017), first-order vs repeat split, quantiles
-- insight: A new customer generates on average BRL 131-162 in the first 12 months, of which only 3-5% comes from repeat orders; the median (BRL 86-99) is far below the mean, i.e. a right-skewed value distribution (p90 BRL 258-350).
-- insight: With under 6% of customers buying again within a year, 12-month value is essentially the first basket: acquisition cost has to be recovered on the first order.
WITH first_orders AS (
    SELECT
        c.customer_key,
        c.first_purchase_date,
        CAST(date_trunc('month', c.first_purchase_date) AS DATE) AS cohort_month
    FROM dim_customer AS c
    WHERE c.first_purchase_date BETWEEN DATE '2017-01-01' AND DATE '2017-08-31'
), window_orders AS (            -- all valid orders inside the customer's first 365 days
    SELECT
        f.customer_key,
        f.cohort_month,
        o.items_value,
        o.customer_order_seq
    FROM first_orders AS f
    JOIN fact_orders  AS o
      ON o.customer_key = f.customer_key
     AND o.is_valid_sale
     AND CAST(o.purchase_ts AS DATE) < f.first_purchase_date + INTERVAL 365 DAY
), per_customer AS (
    SELECT
        customer_key,
        cohort_month,
        sum(items_value)                                         AS value_12m,
        sum(items_value) FILTER (WHERE customer_order_seq = 1)   AS first_order_value,
        count(*)                                                 AS orders_12m
    FROM window_orders
    GROUP BY customer_key, cohort_month
)
SELECT
    strftime(cohort_month, '%Y-%m')                              AS cohort,
    count(*)                                                     AS customers,
    round(avg(first_order_value), 1)                             AS avg_first_order_brl,
    round(avg(value_12m), 1)                                     AS avg_value_12m_brl,
    round(median(value_12m), 1)                                  AS median_value_12m_brl,
    round(quantile_cont(value_12m, 0.9), 1)                      AS p90_value_12m_brl,
    round(100.0 * avg(CASE WHEN orders_12m > 1 THEN 1 ELSE 0 END), 2) AS repeat_within_12m_pct,
    round(100.0 * (sum(value_12m) - sum(first_order_value)) / sum(value_12m), 2) AS repeat_revenue_pct
FROM per_customer
GROUP BY cohort_month
ORDER BY cohort_month;
