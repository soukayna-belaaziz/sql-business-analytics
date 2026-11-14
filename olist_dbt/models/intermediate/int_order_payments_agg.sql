-- Order totals from the payment records (ephemeral).
select
    order_id,
    sum(payment_value)                   as payment_value,
    max(payment_installments)            as max_installments,
    count(*)                             as payment_records,
    -- payment method that covered the largest share of the order value
    arg_max(payment_type, payment_value) as main_payment_type
from {{ ref('clean_order_payments') }}
group by order_id
