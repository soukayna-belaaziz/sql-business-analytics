select
    s.seller_id                    as seller_key,
    s.zip_prefix,
    s.city,
    s.state,
    coalesce(r.region, 'Unknown')  as region
from {{ ref('clean_sellers') }} as s
left join {{ ref('ref_state_region') }} as r on s.state = r.state
