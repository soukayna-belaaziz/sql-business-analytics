-- Order grain. Business definitions used everywhere downstream (queries,
-- dashboard, Power BI):
--   valid sale : status not in (canceled, unavailable) and >= 1 item line
--   revenue    : sum(item price), freight excluded (merchandise revenue, BRL)
--   on-time    : delivered on or before the estimated date
with base as (
    select
        o.order_id,
        c.customer_unique_id                               as customer_key,
        o.order_status,
        o.order_status not in ('canceled', 'unavailable')
            and i.order_id is not null                     as is_valid_sale,
        o.purchase_ts,
        cast(strftime(o.purchase_ts, '%Y%m%d') as integer) as purchase_date_key,
        o.approved_ts,
        o.delivered_carrier_ts,
        o.delivered_customer_ts,
        o.estimated_delivery_date,
        coalesce(i.items_count, 0)                         as items_count,
        coalesce(i.sellers_count, 0)                       as sellers_count,
        coalesce(i.items_value, 0)                         as items_value,
        coalesce(i.freight_value, 0)                       as freight_value,
        coalesce(p.payment_value, 0)                       as payment_value,
        p.max_installments,
        p.main_payment_type,
        r.review_score,
        r.has_comment                                      as review_has_comment
    from {{ ref('clean_orders') }}               as o
    left join {{ ref('clean_customers') }}       as c on o.customer_id = c.customer_id
    left join {{ ref('int_order_items_agg') }}   as i on o.order_id = i.order_id
    left join {{ ref('int_order_payments_agg') }} as p on o.order_id = p.order_id
    left join {{ ref('clean_order_reviews') }}   as r on o.order_id = r.order_id
)
select
    *,
    order_status = 'delivered' and delivered_customer_ts is not null as is_delivered,
    -- lead time in days (decimal) from purchase to delivery at the customer
    case when delivered_customer_ts is not null then
        round(date_diff('minute', purchase_ts, delivered_customer_ts) / 1440.0, 2)
    end as delivery_days,
    -- promised lead time in days
    date_diff('day', cast(purchase_ts as date), estimated_delivery_date) as promised_days,
    -- positive = late, negative = early (calendar days vs estimated date)
    case when delivered_customer_ts is not null then
        date_diff('day', estimated_delivery_date, cast(delivered_customer_ts as date))
    end as delay_days,
    case when delivered_customer_ts is not null then
        cast(delivered_customer_ts as date) <= estimated_delivery_date
    end as is_on_time,
    -- 1 = first valid purchase of this customer, 2 = second, ...
    case when is_valid_sale then
        row_number() over (partition by customer_key, is_valid_sale order by purchase_ts, order_id)
    end as customer_order_seq
from base
