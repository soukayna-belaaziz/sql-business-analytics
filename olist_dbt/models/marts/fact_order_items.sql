-- Order-line grain: revenue, category and seller analysis.
select
    i.order_id,
    i.order_item_id,
    i.product_id                 as product_key,
    i.seller_id                  as seller_key,
    o.customer_key,
    o.purchase_date_key,
    o.order_status,
    o.is_valid_sale,
    i.price,
    i.freight_value,
    i.price + i.freight_value    as gross_value,
    i.shipping_limit_ts,
    -- seller handed the parcel to the carrier after the agreed limit
    case when o.delivered_carrier_ts is not null then
        o.delivered_carrier_ts > i.shipping_limit_ts
    end                          as is_shipped_late
from {{ ref('clean_order_items') }} as i
join {{ ref('fact_orders') }}       as o on i.order_id = o.order_id
