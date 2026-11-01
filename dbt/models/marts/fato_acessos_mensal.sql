{{ config(post_hook=[
    "create index on {{ this }} (mes_referencia, municipio_ibge)",
    "create index on {{ this }} (cnpj, mes_referencia)"
]) }}

select
    mes_referencia,
    cnpj,
    municipio_ibge,
    meio_acesso,
    tipo_pessoa,
    acessos
from {{ ref('stg_anatel__acessos') }}
