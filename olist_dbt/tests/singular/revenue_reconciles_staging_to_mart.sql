-- Revenue reconciliation: item price summed in staging must equal the mart
-- to the cent. Failures = absolute difference in BRL cents.
{{ config(fail_calc = 'coalesce(sum(diff_cents), 0)', meta = {'category': 'reconciliation'}) }}
with s as (select coalesce(sum(price), 0) as v from {{ ref('stg_order_items') }}),
     m as (select coalesce(sum(price), 0) as v from {{ ref('fact_order_items') }})
select cast(abs(s.v - m.v) * 100 as bigint) as diff_cents
from s, m
where s.v <> m.v
