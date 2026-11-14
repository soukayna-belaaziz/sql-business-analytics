-- title: Monthly acquisition cohorts and retention matrix
-- question: Of the customers acquired in a month, what share buys again 1, 2, 3, 6 and 12 months later?
-- technique: cohort assignment from dim_customer, date_diff in months, conditional aggregation into a matrix; cells that are not yet observable are NULL, not 0
-- insight: Retention is very low in every cohort: fewer than 1% of new customers buy again in any given later month (M1 between 0.22% and 0.71%).
-- insight: The marketplace grows through acquisition, not repeat purchase - this is the quantitative case for a CRM / retention programme.
WITH activity AS (               -- distinct (customer, month) with a valid purchase
    SELECT DISTINCT
        o.customer_key,
        d.month_start AS activity_month
    FROM fact_orders AS o
    JOIN dim_date    AS d ON o.purchase_date_key = d.date_key
    WHERE o.is_valid_sale AND d.is_reporting_period
), cohort AS (                   -- cohort = month of the customer's first ever valid purchase
    SELECT
        customer_key,
        CAST(date_trunc('month', first_purchase_date) AS DATE) AS cohort_month
    FROM dim_customer
    WHERE first_purchase_date BETWEEN DATE '2017-01-01' AND DATE '2018-08-31'
), cohort_activity AS (
    SELECT
        c.cohort_month,
        date_diff('month', c.cohort_month, a.activity_month) AS month_number,
        count(DISTINCT a.customer_key)                       AS active_customers
    FROM cohort   AS c
    JOIN activity AS a USING (customer_key)
    GROUP BY ALL
)
SELECT
    strftime(cohort_month, '%Y-%m') AS cohort,
    max(active_customers) FILTER (WHERE month_number = 0) AS cohort_size,
    -- a cell is observable only if cohort_month + k <= last complete month (2018-08)
    CASE WHEN cohort_month + INTERVAL 1 MONTH <= DATE '2018-08-01' THEN
        round(100.0 * coalesce(max(active_customers) FILTER (WHERE month_number = 1), 0)
              / max(active_customers) FILTER (WHERE month_number = 0), 2)
    END AS m1_pct,
    CASE WHEN cohort_month + INTERVAL 2 MONTH <= DATE '2018-08-01' THEN
        round(100.0 * coalesce(max(active_customers) FILTER (WHERE month_number = 2), 0)
              / max(active_customers) FILTER (WHERE month_number = 0), 2)
    END AS m2_pct,
    CASE WHEN cohort_month + INTERVAL 3 MONTH <= DATE '2018-08-01' THEN
        round(100.0 * coalesce(max(active_customers) FILTER (WHERE month_number = 3), 0)
              / max(active_customers) FILTER (WHERE month_number = 0), 2)
    END AS m3_pct,
    CASE WHEN cohort_month + INTERVAL 6 MONTH <= DATE '2018-08-01' THEN
        round(100.0 * coalesce(max(active_customers) FILTER (WHERE month_number = 6), 0)
              / max(active_customers) FILTER (WHERE month_number = 0), 2)
    END AS m6_pct,
    CASE WHEN cohort_month + INTERVAL 12 MONTH <= DATE '2018-08-01' THEN
        round(100.0 * coalesce(max(active_customers) FILTER (WHERE month_number = 12), 0)
              / max(active_customers) FILTER (WHERE month_number = 0), 2)
    END AS m12_pct
FROM cohort_activity
GROUP BY cohort_month
ORDER BY cohort_month;
