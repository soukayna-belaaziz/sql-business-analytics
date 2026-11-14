-- =============================================================================
-- Layer 1: STAGING
-- One table per source CSV, loaded "as is" but with explicit column types.
-- No business logic here: the goal is a typed, queryable copy of the source.
-- `{raw_dir}` is replaced by the Python loader (src/build_db.py) with the
-- folder that holds the CSV files (data/raw for the real data, a fixture
-- folder in the tests).
-- =============================================================================

CREATE OR REPLACE TABLE stg_customers AS
SELECT *
FROM read_csv('{raw_dir}/olist_customers_dataset.csv',
    header = true,
    columns = {
        'customer_id': 'VARCHAR',
        'customer_unique_id': 'VARCHAR',
        'customer_zip_code_prefix': 'VARCHAR',   -- keep leading zeros
        'customer_city': 'VARCHAR',
        'customer_state': 'VARCHAR'
    });

CREATE OR REPLACE TABLE stg_orders AS
SELECT *
FROM read_csv('{raw_dir}/olist_orders_dataset.csv',
    header = true,
    columns = {
        'order_id': 'VARCHAR',
        'customer_id': 'VARCHAR',
        'order_status': 'VARCHAR',
        'order_purchase_timestamp': 'TIMESTAMP',
        'order_approved_at': 'TIMESTAMP',
        'order_delivered_carrier_date': 'TIMESTAMP',
        'order_delivered_customer_date': 'TIMESTAMP',
        'order_estimated_delivery_date': 'TIMESTAMP'
    });

CREATE OR REPLACE TABLE stg_order_items AS
SELECT *
FROM read_csv('{raw_dir}/olist_order_items_dataset.csv',
    header = true,
    columns = {
        'order_id': 'VARCHAR',
        'order_item_id': 'INTEGER',
        'product_id': 'VARCHAR',
        'seller_id': 'VARCHAR',
        'shipping_limit_date': 'TIMESTAMP',
        'price': 'DECIMAL(12,2)',
        'freight_value': 'DECIMAL(12,2)'
    });

CREATE OR REPLACE TABLE stg_order_payments AS
SELECT *
FROM read_csv('{raw_dir}/olist_order_payments_dataset.csv',
    header = true,
    columns = {
        'order_id': 'VARCHAR',
        'payment_sequential': 'INTEGER',
        'payment_type': 'VARCHAR',
        'payment_installments': 'INTEGER',
        'payment_value': 'DECIMAL(12,2)'
    });

CREATE OR REPLACE TABLE stg_order_reviews AS
SELECT *
FROM read_csv('{raw_dir}/olist_order_reviews_dataset.csv',
    header = true,
    columns = {
        'review_id': 'VARCHAR',
        'order_id': 'VARCHAR',
        'review_score': 'INTEGER',
        'review_comment_title': 'VARCHAR',
        'review_comment_message': 'VARCHAR',
        'review_creation_date': 'TIMESTAMP',
        'review_answer_timestamp': 'TIMESTAMP'
    });

CREATE OR REPLACE TABLE stg_products AS
SELECT *
FROM read_csv('{raw_dir}/olist_products_dataset.csv',
    header = true,
    columns = {
        'product_id': 'VARCHAR',
        'product_category_name': 'VARCHAR',
        'product_name_lenght': 'INTEGER',          -- typo is in the source
        'product_description_lenght': 'INTEGER',
        'product_photos_qty': 'INTEGER',
        'product_weight_g': 'INTEGER',
        'product_length_cm': 'INTEGER',
        'product_height_cm': 'INTEGER',
        'product_width_cm': 'INTEGER'
    });

CREATE OR REPLACE TABLE stg_sellers AS
SELECT *
FROM read_csv('{raw_dir}/olist_sellers_dataset.csv',
    header = true,
    columns = {
        'seller_id': 'VARCHAR',
        'seller_zip_code_prefix': 'VARCHAR',
        'seller_city': 'VARCHAR',
        'seller_state': 'VARCHAR'
    });

-- The translation file starts with a UTF-8 BOM; with header = true and
-- explicit column names the header line (BOM included) is simply skipped.
CREATE OR REPLACE TABLE stg_category_translation AS
SELECT *
FROM read_csv('{raw_dir}/product_category_name_translation.csv',
    header = true,
    columns = {
        'product_category_name': 'VARCHAR',
        'product_category_name_english': 'VARCHAR'
    });
