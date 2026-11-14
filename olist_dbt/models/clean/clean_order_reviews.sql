-- The source has orders with more than one review (and review_ids reused
-- across orders). Rule: keep the latest answered review per order, so the mart
-- has at most one score per order.
select
    trim(review_id)          as review_id,
    trim(order_id)           as order_id,
    review_score,
    review_comment_message is not null and length(trim(review_comment_message)) > 0
                             as has_comment,
    review_creation_date     as review_created_ts,
    review_answer_timestamp  as review_answered_ts
from {{ ref('stg_order_reviews') }}
where review_score between 1 and 5
qualify row_number() over (
    partition by order_id
    order by review_answer_timestamp desc nulls last, review_creation_date desc, review_id
) = 1
