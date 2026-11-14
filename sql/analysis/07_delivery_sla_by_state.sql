-- title: Delivery SLA by customer state
-- question: In which states does the logistics network miss the promised delivery date most often?
-- technique: join fact -> dim_customer, conditional averages, HAVING to drop tiny states, RANK() window
-- insight: On-time delivery ranges from 95.9% (PR) and 95.5% (SP) down to 78.5% in Alagoas (AL); 8 of the 9 worst states are in the Northeast, where delivery takes 19-25 days versus 8.7 in Sao Paulo.
-- insight: Even with promised lead times above 30 days the Northeast misses more often, and reviews follow (3.8-3.9 vs 4.25 in SP).
SELECT
    c.state,
    c.region,
    count(*)                                                        AS delivered_orders,
    round(avg(o.delivery_days), 1)                                  AS avg_delivery_days,
    round(avg(o.promised_days), 1)                                  AS avg_promised_days,
    round(100.0 * avg(CASE WHEN o.is_on_time THEN 1 ELSE 0 END), 1) AS on_time_pct,
    round(avg(o.review_score), 2)                                   AS avg_review,
    RANK() OVER (ORDER BY avg(CASE WHEN o.is_on_time THEN 1 ELSE 0 END)) AS worst_rank
FROM fact_orders  AS o
JOIN dim_customer AS c ON o.customer_key = c.customer_key
JOIN dim_date     AS d ON o.purchase_date_key = d.date_key
WHERE o.is_delivered AND d.is_reporting_period
GROUP BY c.state, c.region
HAVING count(*) >= 300
ORDER BY on_time_pct;
