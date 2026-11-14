select
    product_id                        as product_key,
    category,
    category_pt,
    photos_qty,
    weight_g,
    length_cm * height_cm * width_cm  as volume_cm3
from {{ ref('clean_products') }}
