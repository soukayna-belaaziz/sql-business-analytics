-- Reconciliation targets for the Power BI build: the same KPIs as the DAX
-- measures in powerbi/POWERBI_GUIDE.md, computed in SQL on the reporting
-- period (2017-01 .. 2018-08). The Power BI cards must show these values.
WITH o AS (
    SELECT o.*
    FROM fact_orders AS o
    JOIN dim_date    AS d ON o.purchase_date_key = d.date_key
    WHERE o.is_valid_sale AND d.is_reporting_period
), i AS (
    SELECT f.*
    FROM fact_order_items AS f
    JOIN dim_date         AS d ON f.purchase_date_key = d.date_key
    WHERE f.is_valid_sale AND d.is_reporting_period
), aug AS (
    SELECT
        sum(f.price) FILTER (WHERE d.year_month = '2018-08') AS rev_2018_08,
        sum(f.price) FILTER (WHERE d.year_month = '2017-08') AS rev_2017_08
    FROM fact_order_items AS f
    JOIN dim_date         AS d ON f.purchase_date_key = d.date_key
    WHERE f.is_valid_sale
)
SELECT measure, value FROM (
    SELECT 1 AS k, 'Total Revenue (BRL)' AS measure, round((SELECT sum(price) FROM i), 2) AS value
    UNION ALL SELECT 2, 'Orders', (SELECT count(*) FROM o)
    UNION ALL SELECT 3, 'Customers', (SELECT count(DISTINCT customer_key) FROM o)
    UNION ALL SELECT 4, 'AOV (BRL)', round((SELECT sum(price) FROM i) / (SELECT count(*) FROM o), 2)
    UNION ALL SELECT 5, 'Freight % of Revenue', round(100 * (SELECT sum(freight_value) / sum(price) FROM i), 2)
    UNION ALL SELECT 6, 'Repeat Customer Rate %', round(100.0 *
        (SELECT count(*) FROM (SELECT customer_key FROM o GROUP BY 1 HAVING count(*) >= 2))
        / (SELECT count(DISTINCT customer_key) FROM o), 2)
    UNION ALL SELECT 7, 'On-time Delivery %', round(100 * (SELECT avg(CASE WHEN is_on_time THEN 1.0 ELSE 0.0 END)
        FROM o WHERE is_delivered), 2)
    UNION ALL SELECT 8, 'Avg Review Score', round((SELECT avg(review_score) FROM o), 3)
    UNION ALL SELECT 9, 'Late Shipping % (seller)', round(100 * (SELECT avg(CASE WHEN is_shipped_late THEN 1.0 ELSE 0.0 END)
        FROM i WHERE is_shipped_late IS NOT NULL), 2)
    UNION ALL SELECT 10, 'Revenue YoY % (Aug 2018 vs Aug 2017)',
        round(100 * ((SELECT rev_2018_08 FROM aug) / (SELECT rev_2017_08 FROM aug) - 1), 1)
)
ORDER BY k;
