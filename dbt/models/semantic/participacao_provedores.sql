select
    participacao.mes_referencia,
    municipios.municipio,
    municipios.uf,
    municipios.regiao,
    participacao.municipio_ibge,
    participacao.agente_economico,
    agentes.agente_nome,
    participacao.acessos,
    round(participacao.market_share_pct::numeric, 2) as market_share_pct,
    participacao.posicao
from {{ ref('fato_participacao_agente') }} as participacao
inner join {{ ref('dim_municipio') }} as municipios using (municipio_ibge)
inner join {{ ref('dim_agente') }} as agentes using (agente_economico)
