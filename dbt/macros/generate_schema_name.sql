{# Schema names without the target prefix, so OMOP tables land in `omop`, not `main_omop`. #}
{% macro generate_schema_name(custom_schema_name, node) -%}
  {{ custom_schema_name if custom_schema_name else target.schema }}
{%- endmacro %}
