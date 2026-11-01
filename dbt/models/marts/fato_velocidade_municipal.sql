{{ config(post_hook=["create index on {{ this }} (mes_referencia, municipio_ibge)"]) }}

select * from {{ ref('stg_anatel__faixas') }}
