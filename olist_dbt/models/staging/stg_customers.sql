-- Typed copy of the source; no business logic in staging.
select
    cast(customer_id as varchar)              as customer_id,
    cast(customer_unique_id as varchar)       as customer_unique_id,
    cast(customer_zip_code_prefix as varchar) as customer_zip_code_prefix,  -- keep leading zeros
    cast(customer_city as varchar)            as customer_city,
    cast(customer_state as varchar)           as customer_state
from {{ source('olist_raw', 'customers') }}
