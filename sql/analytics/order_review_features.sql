-- Analysis dataset for the delivery-delay -> review-score study (src/causal.py).
-- Grain: one delivered, reviewed, valid-sale order in the reporting period.
-- Only pre-treatment covariates are kept as controls (known at purchase time:
-- what was bought, from whom, where it ships, the promised lead time, when).
-- Lead time itself is NOT a control: it is how the delay happens (a mediator).
WITH main_item AS (
    -- the order's highest-value line defines its main seller and category
    SELECT
        f.order_id,
        arg_max(f.seller_key, f.price)   AS seller_key,
        arg_max(p.category, f.price)     AS category
    FROM fact_order_items AS f
    JOIN dim_product      AS p ON f.product_key = p.product_key
    GROUP BY f.order_id
)
SELECT
    o.order_id,
    o.review_score,
    CAST(o.review_score <= 2 AS INTEGER)            AS is_negative,
    o.delay_days,
    CAST(o.delay_days > 0 AS INTEGER)               AS is_late,
    o.promised_days,
    o.items_value,
    o.freight_value,
    o.items_count,
    CAST(o.sellers_count > 1 AS INTEGER)            AS multi_seller,
    coalesce(o.main_payment_type, 'unknown')        AS payment_type,
    coalesce(o.max_installments, 1)                 AS installments,
    d.year_month                                    AS purchase_month,
    c.state                                         AS customer_state,
    c.region                                        AS customer_region,
    s.state                                         AS seller_state,
    CAST(c.state = s.state AS INTEGER)              AS same_state,
    m.seller_key,
    m.category,
    -- descriptive only (post-treatment): survey answered before the parcel arrived
    CAST(r.review_created_ts < o.delivered_customer_ts AS INTEGER) AS reviewed_before_delivery
FROM fact_orders  AS o
JOIN dim_date     AS d ON o.purchase_date_key = d.date_key
JOIN dim_customer AS c ON o.customer_key = c.customer_key
JOIN main_item    AS m ON o.order_id = m.order_id
JOIN dim_seller   AS s ON m.seller_key = s.seller_key
LEFT JOIN clean_order_reviews AS r ON o.order_id = r.order_id
WHERE o.is_valid_sale
  AND o.delivered_customer_ts IS NOT NULL
  AND o.review_score IS NOT NULL
  AND d.is_reporting_period
ORDER BY o.order_id
