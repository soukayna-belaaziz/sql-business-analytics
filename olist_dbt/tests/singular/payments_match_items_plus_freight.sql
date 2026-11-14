-- Known source issue (warning): order payments differ from items + freight
-- by more than 1 BRL (vouchers, instalment interest). Payments are therefore
-- never used as revenue.
{{ config(severity = 'warn', meta = {'category': 'consistency'}) }}
select order_id, payment_value, items_value, freight_value
from {{ ref('fact_orders') }}
where items_count > 0 and payment_value > 0
  and abs(payment_value - items_value - freight_value) > 1
