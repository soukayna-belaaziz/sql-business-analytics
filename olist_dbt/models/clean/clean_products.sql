-- Attach the English category. Two Portuguese categories have no row in the
-- translation file; they are translated here explicitly. Products without any
-- category are labelled 'unknown' (kept, not dropped).
select
    trim(p.product_id)                            as product_id,
    coalesce(p.product_category_name, 'unknown')  as category_pt,
    coalesce(
        t.product_category_name_english,
        case p.product_category_name
            when 'pc_gamer' then 'pc_gamer'
            when 'portateis_cozinha_e_preparadores_de_alimentos'
                then 'portable_kitchen_food_preparers'
        end,
        'unknown')                                as category,
    p.product_photos_qty                          as photos_qty,
    p.product_weight_g                            as weight_g,
    p.product_length_cm                           as length_cm,
    p.product_height_cm                           as height_cm,
    p.product_width_cm                            as width_cm
from {{ ref('stg_products') }} as p
left join {{ ref('stg_category_translation') }} as t
       on p.product_category_name = t.product_category_name
qualify row_number() over (partition by p.product_id order by p.product_category_name) = 1
