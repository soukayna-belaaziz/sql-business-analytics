select
    trim(order_id)                    as order_id,
    payment_sequential,
    lower(trim(payment_type))         as payment_type,
    -- 0 installments appears for a handful of card payments: treat as 1
    greatest(payment_installments, 1) as payment_installments,
    payment_value
from {{ ref('stg_order_payments') }}
qualify row_number() over (partition by order_id, payment_sequential order by payment_value desc) = 1
