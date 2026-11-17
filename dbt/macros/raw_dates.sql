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

{# The local wall-clock timestamp when the value carries a time, null otherwise. #}
{% macro raw_timestamp(column) -%}
  case when length({{ column }}) >= 19 then cast(substr({{ column }}, 1, 19) as timestamp) end
{%- endmacro %}

{#
  OMOP requires a date on every event, but a Safe Harbor zone keeps only the year. When
  the day is unknown the first day of that year is used, and `load_metadata` records that
  dates in this build are year precision, so nobody reads January 1 as a real visit day.
#}
{% macro event_date(date_column, year_column) -%}
  coalesce({{ date_column }}, {% if target.type == 'bigquery' %}date({{ year_column }}, 1, 1){% else %}make_date({{ year_column }}, 1, 1){% endif %})
{%- endmacro %}
