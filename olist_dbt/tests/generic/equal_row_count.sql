{#- Row-count reconciliation: number of failures = absolute row difference,
    so a join that silently drops 3 rows reports 3 failing rows. -#}
{% test equal_row_count(model, compare_model) %}
{{ config(fail_calc = 'coalesce(sum(row_diff), 0)') }}
with a as (select count(*) as n from {{ model }}),
     b as (select count(*) as n from {{ compare_model }})
select abs(a.n - b.n) as row_diff
from a, b
where a.n <> b.n
{% endtest %}
