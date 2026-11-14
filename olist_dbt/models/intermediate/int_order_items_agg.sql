-- Order totals from the item lines (ephemeral: inlined as a CTE where used).
select
    order_id,
    count(*)                  as items_count,
    count(distinct seller_id) as sellers_count,
    sum(price)                as items_value,
    sum(freight_value)        as freight_value
from {{ ref('clean_order_items') }}
group by order_id
