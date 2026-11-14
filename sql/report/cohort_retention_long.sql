-- Long-form cohort retention (cohort x month_number 0..12) used by the
-- heatmap in the KPI report. Same logic as sql/analysis/03_cohort_retention.sql.
WITH activity AS (
    SELECT DISTINCT o.customer_key, d.month_start AS activity_month
    FROM fact_orders AS o
    JOIN dim_date    AS d ON o.purchase_date_key = d.date_key
    WHERE o.is_valid_sale AND d.is_reporting_period
), cohort AS (
    SELECT customer_key,
           CAST(date_trunc('month', first_purchase_date) AS DATE) AS cohort_month
    FROM dim_customer
    WHERE first_purchase_date BETWEEN DATE '2017-01-01' AND DATE '2018-08-31'
), counts AS (
    SELECT c.cohort_month,
           date_diff('month', c.cohort_month, a.activity_month) AS month_number,
           count(DISTINCT a.customer_key) AS active_customers
    FROM cohort AS c JOIN activity AS a USING (customer_key)
    GROUP BY ALL
)
SELECT
    strftime(cohort_month, '%Y-%m') AS cohort,
    month_number,
    active_customers,
    100.0 * active_customers
        / max(active_customers) FILTER (WHERE month_number = 0) OVER (PARTITION BY cohort_month)
        AS retention_pct
FROM counts
WHERE month_number <= 12
ORDER BY cohort, month_number;
