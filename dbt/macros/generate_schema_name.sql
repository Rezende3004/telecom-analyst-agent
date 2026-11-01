{# Usa o nome da pasta como schema, sem o prefixo que o dbt coloca por padrão. #}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {{ custom_schema_name | trim if custom_schema_name else target.schema }}
{%- endmacro %}
