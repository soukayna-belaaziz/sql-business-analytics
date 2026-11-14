-- title: Daily revenue anomaly flags
-- question: Which days had revenue far outside the recent normal range (promotions, outages, data gaps)?
-- technique: daily series on dim_date (days without sales kept as 0 via LEFT JOIN), trailing 28-day mean and standard deviation that exclude the current day, z-score flag |z| > 3
-- insight: Seven days exceed |z| > 3 against the trailing 28-day mean, all spikes and no drops. Black Friday 2017-11-24 is the extreme outlier: BRL 152.7k, 6.3 times the trailing mean (z = 18.6), with 20 and 23 November also flagged.
-- insight: Flagged days should be labelled as promotions (or excluded) before the series is used for forecasting or target setting.
WITH daily AS (
    SELECT
        d.date,
        d.weekday_name,
        coalesce(sum(o.items_value), 0) AS revenue,
        count(o.order_id)               AS orders
    FROM dim_date AS d
    LEFT JOIN fact_orders AS o
           ON o.purchase_date_key = d.date_key AND o.is_valid_sale
    WHERE d.is_reporting_period
    GROUP BY d.date, d.weekday_name
), stats AS (
    SELECT
        *,
        avg(revenue)        OVER w AS mean_28d,
        stddev_samp(revenue) OVER w AS sd_28d
    FROM daily
    WINDOW w AS (ORDER BY date ROWS BETWEEN 28 PRECEDING AND 1 PRECEDING)
)
SELECT
    date,
    weekday_name,
    orders,
    round(revenue, 0)                         AS revenue_brl,
    round(mean_28d, 0)                        AS trailing_28d_mean,
    round((revenue - mean_28d) / sd_28d, 1)   AS z_score,
    CASE WHEN revenue > mean_28d THEN 'spike' ELSE 'drop' END AS flag
FROM stats
WHERE date >= DATE '2017-01-29'               -- first day with a full 28-day history
  AND abs((revenue - mean_28d) / sd_28d) > 3
ORDER BY date;
