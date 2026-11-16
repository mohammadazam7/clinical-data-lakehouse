{#
  OMOP keys are integers; the raw zone carries keyed-hash pseudonyms (hex strings). The
  first 15 hex digits (60 bits) are read as a number, so a key depends only on the
  pseudonym: the same person gets the same person_id on every load and in every table,
  with no lookup table to keep in step. A uniqueness test on each key guards against the
  very unlikely collision.
#}
{% macro surrogate_id(column) -%}
  cast(concat('0x', substr(replace({{ column }}, '-', ''), 1, 15)) as bigint)
{%- endmacro %}
