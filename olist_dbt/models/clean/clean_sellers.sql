select
    trim(seller_id)                            as seller_id,
    lpad(trim(seller_zip_code_prefix), 5, '0') as zip_prefix,
    lower(trim(seller_city))                   as city,
    upper(trim(seller_state))                  as state
from {{ ref('stg_sellers') }}
qualify row_number() over (partition by seller_id order by seller_city) = 1
