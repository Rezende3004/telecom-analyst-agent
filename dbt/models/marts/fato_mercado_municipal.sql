{{ config(post_hook=["create unique index on {{ this }} (mes_referencia, municipio_ibge)"]) }}

-- HHI na escala de 0 a 10.000, somando o quadrado do market share em pontos percentuais.
-- A penetração usa domicílios do Censo 2022, então passa de 100 em mercados com muitos
-- acessos corporativos ou com domicílios novos desde o censo.
with concentracao as (
    select
        mes_referencia,
        municipio_ibge,
        sum(acessos) as acessos,
        count(*) as provedores,
        sum(market_share_pct ^ 2) as hhi,
        max(market_share_pct) as share_lider_pct
    from {{ ref('fato_participacao_agente') }}
    group by 1, 2
),

lideres as (
    select distinct on (mes_referencia, municipio_ibge)
        mes_referencia,
        municipio_ibge,
        agente_economico as lider
    from {{ ref('fato_participacao_agente') }}
    where posicao = 1
    order by mes_referencia, municipio_ibge, agente_economico
),

residencial as (
    select
        mes_referencia,
        municipio_ibge,
        sum(acessos) as acessos_pessoa_fisica
    from {{ ref('fato_acessos_mensal') }}
    where tipo_pessoa = 'Pessoa Física'
    group by 1, 2
)

select
    concentracao.mes_referencia,
    concentracao.municipio_ibge,
    concentracao.acessos,
    residencial.acessos_pessoa_fisica,
    100.0 * concentracao.acessos / nullif(municipios.domicilios, 0) as penetracao_domicilios,
    100.0 * residencial.acessos_pessoa_fisica
        / nullif(municipios.domicilios, 0) as penetracao_residencial,
    concentracao.provedores,
    lideres.lider,
    concentracao.share_lider_pct,
    concentracao.hhi,
    case
        when concentracao.hhi < 1500 then 'não concentrado'
        when concentracao.hhi <= 2500 then 'moderadamente concentrado'
        else 'altamente concentrado'
    end as nivel_concentracao,
    100.0 * (concentracao.acessos::numeric / nullif(ano_anterior.acessos, 0) - 1)
        as crescimento_12m_pct
from concentracao
inner join lideres using (mes_referencia, municipio_ibge)
inner join {{ ref('dim_municipio') }} as municipios using (municipio_ibge)
left join residencial using (mes_referencia, municipio_ibge)
-- Pela data, e não por lag: há municípios com meses faltando e a série começa trimestral.
left join concentracao as ano_anterior
    on concentracao.municipio_ibge = ano_anterior.municipio_ibge
    and ano_anterior.mes_referencia = (concentracao.mes_referencia - interval '12 months')::date
