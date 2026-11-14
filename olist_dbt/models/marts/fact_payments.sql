-- Payment-record grain (one row per payment method used on an order).
select
    p.order_id,
    p.payment_sequential,
    p.payment_type,
    p.payment_installments,
    p.payment_value,
    o.customer_key,
    o.purchase_date_key,
    o.is_valid_sale
from {{ ref('clean_order_payments') }} as p
join {{ ref('fact_orders') }}          as o on p.order_id = o.order_id
