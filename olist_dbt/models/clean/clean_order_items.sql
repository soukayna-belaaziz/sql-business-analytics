select
    trim(order_id)        as order_id,
    order_item_id,
    trim(product_id)      as product_id,
    trim(seller_id)       as seller_id,
    shipping_limit_date   as shipping_limit_ts,
    price,
    freight_value
from {{ ref('stg_order_items') }}
qualify row_number() over (partition by order_id, order_item_id order by product_id) = 1
