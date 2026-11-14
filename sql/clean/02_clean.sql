-- =============================================================================
-- Layer 2: CLEAN
-- Standardise text, resolve duplicates, fill documented gaps. Each table keeps
-- the grain of its source except where a rule below says otherwise.
-- =============================================================================

-- Brazilian state -> IBGE macro-region. Used by customer and seller dims.
CREATE OR REPLACE TABLE ref_state_region AS
SELECT * FROM (VALUES
    ('AC', 'North'), ('AP', 'North'), ('AM', 'North'), ('PA', 'North'),
    ('RO', 'North'), ('RR', 'North'), ('TO', 'North'),
    ('AL', 'Northeast'), ('BA', 'Northeast'), ('CE', 'Northeast'),
    ('MA', 'Northeast'), ('PB', 'Northeast'), ('PE', 'Northeast'),
    ('PI', 'Northeast'), ('RN', 'Northeast'), ('SE', 'Northeast'),
    ('DF', 'Center-West'), ('GO', 'Center-West'), ('MT', 'Center-West'),
    ('MS', 'Center-West'),
    ('ES', 'Southeast'), ('MG', 'Southeast'), ('RJ', 'Southeast'),
    ('SP', 'Southeast'),
    ('PR', 'South'), ('RS', 'South'), ('SC', 'South')
) AS t(state, region);

-- Customers: one row per customer_id (= one row per order in Olist).
-- customer_unique_id identifies the real person across orders.
CREATE OR REPLACE TABLE clean_customers AS
SELECT
    trim(customer_id)                         AS customer_id,
    trim(customer_unique_id)                  AS customer_unique_id,
    lpad(trim(customer_zip_code_prefix), 5, '0') AS zip_prefix,
    lower(trim(customer_city))                AS city,
    upper(trim(customer_state))               AS state
FROM stg_customers
QUALIFY row_number() OVER (PARTITION BY customer_id ORDER BY customer_unique_id) = 1;

-- Orders: normalise status; keep every order (status drives the sales flag
-- in the mart, not a filter here, so totals can always be reconciled).
CREATE OR REPLACE TABLE clean_orders AS
SELECT
    trim(order_id)                   AS order_id,
    trim(customer_id)                AS customer_id,
    lower(trim(order_status))        AS order_status,
    order_purchase_timestamp         AS purchase_ts,
    order_approved_at                AS approved_ts,
    order_delivered_carrier_date     AS delivered_carrier_ts,
    order_delivered_customer_date    AS delivered_customer_ts,
    CAST(order_estimated_delivery_date AS DATE) AS estimated_delivery_date
FROM stg_orders
QUALIFY row_number() OVER (PARTITION BY order_id ORDER BY order_purchase_timestamp) = 1;

CREATE OR REPLACE TABLE clean_order_items AS
SELECT
    trim(order_id)        AS order_id,
    order_item_id,
    trim(product_id)      AS product_id,
    trim(seller_id)       AS seller_id,
    shipping_limit_date   AS shipping_limit_ts,
    price,
    freight_value
FROM stg_order_items
QUALIFY row_number() OVER (PARTITION BY order_id, order_item_id ORDER BY product_id) = 1;

CREATE OR REPLACE TABLE clean_order_payments AS
SELECT
    trim(order_id)               AS order_id,
    payment_sequential,
    lower(trim(payment_type))    AS payment_type,
    -- 0 installments appears for a handful of card payments: treat as 1
    greatest(payment_installments, 1) AS payment_installments,
    payment_value
FROM stg_order_payments
QUALIFY row_number() OVER (PARTITION BY order_id, payment_sequential ORDER BY payment_value DESC) = 1;

-- Reviews: the source has a few orders with more than one review (and a few
-- review_ids reused across orders). Rule: keep the latest answered review per
-- order, so that the mart has at most one score per order.
CREATE OR REPLACE TABLE clean_order_reviews AS
SELECT
    trim(review_id)          AS review_id,
    trim(order_id)           AS order_id,
    review_score,
    review_comment_message IS NOT NULL AND length(trim(review_comment_message)) > 0
                             AS has_comment,
    review_creation_date     AS review_created_ts,
    review_answer_timestamp  AS review_answered_ts
FROM stg_order_reviews
WHERE review_score BETWEEN 1 AND 5
QUALIFY row_number() OVER (
    PARTITION BY order_id
    ORDER BY review_answer_timestamp DESC NULLS LAST, review_creation_date DESC, review_id
) = 1;

-- Products: attach the English category. Two Portuguese categories have no
-- row in the translation file; they are translated here explicitly.
-- Products without any category are labelled 'unknown' (kept, not dropped).
CREATE OR REPLACE TABLE clean_products AS
SELECT
    trim(p.product_id) AS product_id,
    coalesce(p.product_category_name, 'unknown') AS category_pt,
    coalesce(
        t.product_category_name_english,
        CASE p.product_category_name
            WHEN 'pc_gamer' THEN 'pc_gamer'
            WHEN 'portateis_cozinha_e_preparadores_de_alimentos'
                THEN 'portable_kitchen_food_preparers'
        END,
        'unknown') AS category,
    p.product_photos_qty     AS photos_qty,
    p.product_weight_g       AS weight_g,
    p.product_length_cm      AS length_cm,
    p.product_height_cm      AS height_cm,
    p.product_width_cm       AS width_cm
FROM stg_products AS p
LEFT JOIN stg_category_translation AS t
       ON p.product_category_name = t.product_category_name
QUALIFY row_number() OVER (PARTITION BY p.product_id ORDER BY p.product_category_name) = 1;

CREATE OR REPLACE TABLE clean_sellers AS
SELECT
    trim(seller_id)                          AS seller_id,
    lpad(trim(seller_zip_code_prefix), 5, '0') AS zip_prefix,
    lower(trim(seller_city))                 AS city,
    upper(trim(seller_state))                AS state
FROM stg_sellers
QUALIFY row_number() OVER (PARTITION BY seller_id ORDER BY seller_city) = 1;
