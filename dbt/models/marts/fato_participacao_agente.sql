{{ config(post_hook=[
    "create index on {{ this }} (mes_referencia, municipio_ibge)",
    "create index on {{ this }} (agente_economico, mes_referencia)"
]) }}

select
    mes_referencia,
    municipio_ibge,
    agente_economico,
    acessos,
    100.0 * acessos / sum(acessos) over mercado as market_share_pct,
    rank() over (partition by mes_referencia, municipio_ibge order by acessos desc) as posicao
from {{ ref('int_acessos_agente') }}
window mercado as (partition by mes_referencia, municipio_ibge)
