-- Weekly valid orders (ISO weeks, Monday start) for the demand forecast
-- (src/forecast.py). Only complete, fully extracted weeks: daily orders fall
-- from ~250 to under 100 after 2018-08-22 (the public extract fades out, it is
-- not a real drop), so the series stops at the week of 2018-08-13.
SELECT
    CAST(date_trunc('week', o.purchase_ts) AS DATE) AS week_start,
    count(*)                                        AS orders,
    sum(o.items_value)                              AS revenue_brl
FROM fact_orders AS o
JOIN dim_date    AS d ON o.purchase_date_key = d.date_key
WHERE o.is_valid_sale AND d.is_reporting_period
GROUP BY 1
HAVING week_start >= DATE '2017-01-02'                       -- first Monday of 2017
   AND week_start <= DATE '2018-08-13'                       -- last fully extracted week
ORDER BY 1
