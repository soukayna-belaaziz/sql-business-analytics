-- title: Payment mix and instalments
-- question: How do customers pay, how is the mix shifting, and how many instalments do card buyers use?
-- technique: fact_payments aggregation, share of value with window SUM, FILTER per year for the mix shift
-- insight: Credit card dominates (78.5% of payment value) with 3.5 instalments on average and 21% of card payments in 6+ instalments - instalment credit is central to Brazilian e-commerce.
-- insight: Boleto (bank slip) shrinks from 20.0% to 16.9% of value between Jan-Aug 2017 and Jan-Aug 2018, while debit card grows from 0.5% to 2.0%.
WITH p AS (
    SELECT
        f.payment_type,
        f.order_id,
        f.payment_value,
        f.payment_installments,
        d.year,
        d.month
    FROM fact_payments AS f
    JOIN dim_date      AS d ON f.purchase_date_key = d.date_key
    WHERE f.is_valid_sale AND d.is_reporting_period
)
SELECT
    payment_type,
    count(DISTINCT order_id)                                          AS orders,
    round(sum(payment_value), 0)                                      AS value_brl,
    round(100.0 * sum(payment_value) / sum(sum(payment_value)) OVER (), 1) AS value_pct,
    round(avg(payment_value), 1)                                      AS avg_payment_brl,
    round(avg(payment_installments), 2)                               AS avg_installments,
    round(100.0 * avg(CASE WHEN payment_installments >= 6 THEN 1 ELSE 0 END), 1) AS six_plus_installments_pct,
    round(100.0 * sum(payment_value) FILTER (WHERE year = 2017 AND month <= 8)
          / sum(sum(payment_value) FILTER (WHERE year = 2017 AND month <= 8)) OVER (), 1) AS value_pct_jan_aug_2017,
    round(100.0 * sum(payment_value) FILTER (WHERE year = 2018 AND month <= 8)
          / sum(sum(payment_value) FILTER (WHERE year = 2018 AND month <= 8)) OVER (), 1) AS value_pct_jan_aug_2018
FROM p
GROUP BY payment_type
ORDER BY value_brl DESC;
