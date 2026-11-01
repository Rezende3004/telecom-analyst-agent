select
    mercado.mes_referencia,
    municipios.municipio,
    municipios.uf,
    municipios.regiao,
    mercado.municipio_ibge,
    municipios.populacao,
    municipios.domicilios,
    municipios.renda_per_capita,
    mercado.acessos,
    mercado.acessos_pessoa_fisica,
    round(mercado.penetracao_domicilios::numeric, 2) as penetracao_domicilios,
    round(mercado.penetracao_residencial::numeric, 2) as penetracao_residencial,
    mercado.provedores,
    agentes.agente_nome as lider,
    round(mercado.share_lider_pct::numeric, 2) as share_lider_pct,
    round(mercado.hhi::numeric, 0) as hhi,
    mercado.nivel_concentracao,
    round(mercado.crescimento_12m_pct::numeric, 2) as crescimento_12m_pct
from {{ ref('fato_mercado_municipal') }} as mercado
inner join {{ ref('dim_municipio') }} as municipios using (municipio_ibge)
inner join {{ ref('dim_agente') }} as agentes on mercado.lider = agentes.agente_economico
