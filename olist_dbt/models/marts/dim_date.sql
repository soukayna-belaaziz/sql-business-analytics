-- Calendar from the first purchase to the last purchase / delivery / promise.
with bounds as (
    select
        cast(min(purchase_ts) as date) as d0,
        greatest(
            cast(max(purchase_ts) as date),
            max(estimated_delivery_date),
            cast(max(delivered_customer_ts) as date)) as d1
    from {{ ref('clean_orders') }}
), days as (
    select cast(unnest(generate_series(d0, d1, interval 1 day)) as date) as d
    from bounds
)
select
    cast(strftime(d, '%Y%m%d') as integer)  as date_key,
    d                                       as date,
    year(d)                                 as year,
    quarter(d)                              as quarter,
    month(d)                                as month,
    strftime(d, '%b')                       as month_name,
    strftime(d, '%Y-%m')                    as year_month,
    cast(date_trunc('month', d) as date)    as month_start,
    isodow(d)                               as iso_weekday,       -- 1 = Monday
    strftime(d, '%a')                       as weekday_name,
    isodow(d) in (6, 7)                     as is_weekend,
    d between date '{{ var("reporting_start") }}' and date '{{ var("reporting_end") }}'
                                            as is_reporting_period
from days
