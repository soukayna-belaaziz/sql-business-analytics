{#- Fails with one row per record where `expression` is false.
    NULL counts as a pass, like a SQL CHECK constraint. -#}
{% test expression_is_true(model, expression) %}
select *
from {{ model }}
where not coalesce(({{ expression }}), true)
{% endtest %}
