-- title: Monthly revenue, orders and growth
-- question: How fast is the marketplace growing month over month and year over year?
-- technique: monthly aggregation on the star schema, LAG() for MoM and YoY growth, moving average window
-- insight: Revenue grew from BRL 120k in Jan 2017 to a plateau of BRL 0.85-1.0M per month in 2018; Nov 2017 (Black Friday) is the peak month at BRL 1.00M.
-- insight: Growth has stalled since March 2018 (MoM between -13% and +2%) and YoY growth decelerates from +166% in March to +49% in August; the very high Jan-Feb 2018 YoY figures reflect the small early-2017 base, not acceleration.
WITH monthly AS (
    SELECT
        d.month_start,
        d.year_month,
        count(*)            AS orders,
        sum(o.items_value)  AS revenue
    FROM fact_orders AS o
    JOIN dim_date    AS d ON o.purchase_date_key = d.date_key
    WHERE o.is_valid_sale
      AND d.is_reporting_period
    GROUP BY d.month_start, d.year_month
)
SELECT
    year_month,
    orders,
    round(revenue, 0)                                               AS revenue_brl,
    round(revenue / orders, 2)                                      AS aov_brl,
    round(100 * (revenue / LAG(revenue) OVER w - 1), 1)             AS mom_growth_pct,
    -- LAG(.., 12) is only defined from Jan 2018 on (12 months of history needed)
    round(100 * (revenue / LAG(revenue, 12) OVER w - 1), 1)         AS yoy_growth_pct,
    round(avg(revenue) OVER (w ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 0) AS revenue_3m_avg
FROM monthly
WINDOW w AS (ORDER BY month_start)
ORDER BY month_start;
