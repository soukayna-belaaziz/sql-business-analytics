-- Normalise status; keep every order (status drives the sales flag in the
-- mart, not a filter here, so totals can always be reconciled).
select
    trim(order_id)                   as order_id,
    trim(customer_id)                as customer_id,
    lower(trim(order_status))        as order_status,
    order_purchase_timestamp         as purchase_ts,
    order_approved_at                as approved_ts,
    order_delivered_carrier_date     as delivered_carrier_ts,
    order_delivered_customer_date    as delivered_customer_ts,
    cast(order_estimated_delivery_date as date) as estimated_delivery_date
from {{ ref('stg_orders') }}
qualify row_number() over (partition by order_id order by order_purchase_timestamp) = 1
