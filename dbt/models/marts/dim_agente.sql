-- Nome legível de cada agente econômico e seus acessos no mês mais recente.
with nomes as (
    select
        agente_economico,
        min(case when grupo_economico = 'OUTROS' then nome_publico else grupo_economico end)
            as agente_nome,
        count(*) as cnpjs
    from {{ ref('dim_empresa') }}
    group by 1
),

atuais as (
    select
        empresas.agente_economico,
        sum(acessos.acessos) as acessos
    from {{ ref('fato_acessos_mensal') }} as acessos
    inner join {{ ref('dim_empresa') }} as empresas using (cnpj)
    where acessos.mes_referencia = (select max(mes_referencia) from {{ ref('dim_tempo') }})
    group by 1
)

select
    nomes.agente_economico,
    nomes.agente_nome,
    nomes.cnpjs,
    coalesce(atuais.acessos, 0) as acessos_atuais
from nomes
left join atuais using (agente_economico)
