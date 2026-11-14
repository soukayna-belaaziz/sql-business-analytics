-- =============================================================================
-- Layer 3: MART (star schema)
--
--   dim_date ─┐
--   dim_customer ─┼── fact_orders (1 row per order) ──┐
--                 │                                   ├── fact_order_items (1 row per order line)
--   dim_product ──┼───────────────────────────────────┘     │
--   dim_seller ───┘─────────────────────────────────────────┘
--                     fact_payments (1 row per payment instalment plan)
--
-- Business definitions (used everywhere downstream, including Power BI):
--   * Valid sale      : order_status NOT IN ('canceled', 'unavailable')
--   * Revenue         : SUM(item price), freight excluded (merchandise revenue, BRL)
--   * Gross value     : price + freight = what the customer paid for the items
--   * On-time         : delivered to customer on or before the estimated date
--   * Reporting period: 2017-01-01 .. 2018-08-31 (complete months only; 2016
--                       is a soft-launch with a gap, Sep/Oct 2018 are a
--                       truncated extraction with 20 orders in total)
-- =============================================================================

-- ---------------------------------------------------------------- dim_date --
CREATE OR REPLACE TABLE dim_date AS
WITH bounds AS (
    SELECT
        CAST(min(purchase_ts) AS DATE) AS d0,
        greatest(
            CAST(max(purchase_ts) AS DATE),
            max(estimated_delivery_date),
            CAST(max(delivered_customer_ts) AS DATE)) AS d1
    FROM clean_orders
), days AS (
    SELECT CAST(unnest(generate_series(d0, d1, INTERVAL 1 DAY)) AS DATE) AS d
    FROM bounds
)
SELECT
    CAST(strftime(d, '%Y%m%d') AS INTEGER)  AS date_key,
    d                                       AS date,
    year(d)                                 AS year,
    quarter(d)                              AS quarter,
    month(d)                                AS month,
    strftime(d, '%b')                       AS month_name,
    strftime(d, '%Y-%m')                    AS year_month,
    CAST(date_trunc('month', d) AS DATE)    AS month_start,
    isodow(d)                               AS iso_weekday,       -- 1 = Monday
    strftime(d, '%a')                       AS weekday_name,
    isodow(d) IN (6, 7)                     AS is_weekend,
    d BETWEEN DATE '2017-01-01' AND DATE '2018-08-31' AS is_reporting_period
FROM days;

-- ------------------------------------------------------------- dim_seller --
CREATE OR REPLACE TABLE dim_seller AS
SELECT
    s.seller_id                         AS seller_key,
    s.zip_prefix,
    s.city,
    s.state,
    coalesce(r.region, 'Unknown')       AS region
FROM clean_sellers AS s
LEFT JOIN ref_state_region AS r ON s.state = r.state;

-- ------------------------------------------------------------ dim_product --
CREATE OR REPLACE TABLE dim_product AS
SELECT
    product_id   AS product_key,
    category,
    category_pt,
    photos_qty,
    weight_g,
    length_cm * height_cm * width_cm AS volume_cm3
FROM clean_products;

-- ---------------------------------------------- helper: order-level facts --
-- Order totals from items and payments, computed once and reused.
CREATE OR REPLACE TEMP TABLE _order_items_agg AS
SELECT
    order_id,
    count(*)                       AS items_count,
    count(DISTINCT seller_id)      AS sellers_count,
    sum(price)                     AS items_value,
    sum(freight_value)             AS freight_value
FROM clean_order_items
GROUP BY order_id;

CREATE OR REPLACE TEMP TABLE _order_payments_agg AS
SELECT
    order_id,
    sum(payment_value)             AS payment_value,
    max(payment_installments)      AS max_installments,
    count(*)                       AS payment_records,
    -- payment method that covered the largest share of the order value
    arg_max(payment_type, payment_value) AS main_payment_type
FROM clean_order_payments
GROUP BY order_id;

-- ------------------------------------------------------------ fact_orders --
CREATE OR REPLACE TABLE fact_orders AS
WITH base AS (
    SELECT
        o.order_id,
        c.customer_unique_id                               AS customer_key,
        o.order_status,
        o.order_status NOT IN ('canceled', 'unavailable')  AS is_valid_sale,
        o.purchase_ts,
        CAST(strftime(o.purchase_ts, '%Y%m%d') AS INTEGER) AS purchase_date_key,
        o.approved_ts,
        o.delivered_carrier_ts,
        o.delivered_customer_ts,
        o.estimated_delivery_date,
        coalesce(i.items_count, 0)                         AS items_count,
        coalesce(i.sellers_count, 0)                       AS sellers_count,
        coalesce(i.items_value, 0)                         AS items_value,
        coalesce(i.freight_value, 0)                       AS freight_value,
        coalesce(p.payment_value, 0)                       AS payment_value,
        p.max_installments,
        p.main_payment_type,
        r.review_score,
        r.has_comment                                      AS review_has_comment
    FROM clean_orders AS o
    LEFT JOIN clean_customers      AS c ON o.customer_id = c.customer_id
    LEFT JOIN _order_items_agg     AS i ON o.order_id = i.order_id
    LEFT JOIN _order_payments_agg  AS p ON o.order_id = p.order_id
    LEFT JOIN clean_order_reviews  AS r ON o.order_id = r.order_id
)
SELECT
    *,
    order_status = 'delivered' AND delivered_customer_ts IS NOT NULL AS is_delivered,
    -- lead time in days (decimal) from purchase to delivery at the customer
    CASE WHEN delivered_customer_ts IS NOT NULL THEN
        round(date_diff('minute', purchase_ts, delivered_customer_ts) / 1440.0, 2)
    END AS delivery_days,
    -- promised lead time in days
    date_diff('day', CAST(purchase_ts AS DATE), estimated_delivery_date) AS promised_days,
    -- positive = late, negative = early (calendar days vs estimated date)
    CASE WHEN delivered_customer_ts IS NOT NULL THEN
        date_diff('day', estimated_delivery_date, CAST(delivered_customer_ts AS DATE))
    END AS delay_days,
    CASE WHEN delivered_customer_ts IS NOT NULL THEN
        CAST(delivered_customer_ts AS DATE) <= estimated_delivery_date
    END AS is_on_time,
    -- 1 = first valid purchase of this customer, 2 = second, ...
    CASE WHEN is_valid_sale THEN
        row_number() OVER (PARTITION BY customer_key, is_valid_sale ORDER BY purchase_ts, order_id)
    END AS customer_order_seq
FROM base;

-- ----------------------------------------------------------- dim_customer --
-- One row per real person (customer_unique_id). Location = the one used on
-- the person's most recent order.
CREATE OR REPLACE TABLE dim_customer AS
WITH latest_location AS (
    SELECT
        c.customer_unique_id,
        c.zip_prefix, c.city, c.state
    FROM clean_customers AS c
    JOIN clean_orders     AS o USING (customer_id)
    QUALIFY row_number() OVER (
        PARTITION BY c.customer_unique_id ORDER BY o.purchase_ts DESC, o.order_id) = 1
), first_sale AS (
    SELECT
        customer_key,
        min(purchase_ts)                    AS first_purchase_ts,
        count(*)                            AS lifetime_orders,
        sum(items_value)                    AS lifetime_revenue
    FROM fact_orders
    WHERE is_valid_sale
    GROUP BY customer_key
)
SELECT
    l.customer_unique_id                         AS customer_key,
    l.zip_prefix,
    l.city,
    l.state,
    coalesce(r.region, 'Unknown')                AS region,
    CAST(f.first_purchase_ts AS DATE)            AS first_purchase_date,
    strftime(f.first_purchase_ts, '%Y-%m')       AS cohort_month,
    coalesce(f.lifetime_orders, 0)               AS lifetime_orders,
    coalesce(f.lifetime_revenue, 0)              AS lifetime_revenue
FROM latest_location AS l
LEFT JOIN ref_state_region AS r ON l.state = r.state
LEFT JOIN first_sale       AS f ON l.customer_unique_id = f.customer_key;

-- ------------------------------------------------------- fact_order_items --
CREATE OR REPLACE TABLE fact_order_items AS
SELECT
    i.order_id,
    i.order_item_id,
    i.product_id                       AS product_key,
    i.seller_id                        AS seller_key,
    o.customer_key,
    o.purchase_date_key,
    o.order_status,
    o.is_valid_sale,
    i.price,
    i.freight_value,
    i.price + i.freight_value          AS gross_value,
    i.shipping_limit_ts,
    -- seller handed the parcel to the carrier after the agreed limit
    CASE WHEN o.delivered_carrier_ts IS NOT NULL THEN
        o.delivered_carrier_ts > i.shipping_limit_ts
    END                                AS is_shipped_late
FROM clean_order_items AS i
JOIN fact_orders       AS o ON i.order_id = o.order_id;

-- ---------------------------------------------------------- fact_payments --
CREATE OR REPLACE TABLE fact_payments AS
SELECT
    p.order_id,
    p.payment_sequential,
    p.payment_type,
    p.payment_installments,
    p.payment_value,
    o.customer_key,
    o.purchase_date_key,
    o.is_valid_sale
FROM clean_order_payments AS p
JOIN fact_orders          AS o ON p.order_id = o.order_id;

DROP TABLE IF EXISTS _order_items_agg;
DROP TABLE IF EXISTS _order_payments_agg;
