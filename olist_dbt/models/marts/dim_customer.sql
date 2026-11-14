-- One row per real person (customer_unique_id). Location = the one used on
-- the person's most recent order.
with latest_location as (
    select c.customer_unique_id, c.zip_prefix, c.city, c.state
    from {{ ref('clean_customers') }} as c
    join {{ ref('clean_orders') }}    as o using (customer_id)
    qualify row_number() over (
        partition by c.customer_unique_id order by o.purchase_ts desc, o.order_id) = 1
), first_sale as (
    select
        customer_key,
        min(purchase_ts)  as first_purchase_ts,
        count(*)          as lifetime_orders,
        sum(items_value)  as lifetime_revenue
    from {{ ref('fact_orders') }}
    where is_valid_sale
    group by customer_key
)
select
    l.customer_unique_id                    as customer_key,
    l.zip_prefix,
    l.city,
    l.state,
    coalesce(r.region, 'Unknown')           as region,
    cast(f.first_purchase_ts as date)       as first_purchase_date,
    strftime(f.first_purchase_ts, '%Y-%m')  as cohort_month,
    coalesce(f.lifetime_orders, 0)          as lifetime_orders,
    coalesce(f.lifetime_revenue, 0)         as lifetime_revenue
from latest_location as l
left join {{ ref('ref_state_region') }} as r on l.state = r.state
left join first_sale                    as f on l.customer_unique_id = f.customer_key
