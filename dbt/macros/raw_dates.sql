{#
  Raw zone dates are strings whose precision depends on the de-identification mode:
  Safe Harbor keeps only the year ('2019'); date shifting keeps full dates or timestamps.
  These macros read either form without inventing precision that is not there.
#}
{% macro raw_year(column) -%}
  cast(substr({{ column }}, 1, 4) as integer)
{%- endmacro %}

{# The date when the value carries one, null when only the year is known. #}
{% macro raw_date(column) -%}
  case when length({{ column }}) >= 10 then cast(substr({{ column }}, 1, 10) as date) end
{%- endmacro %}
