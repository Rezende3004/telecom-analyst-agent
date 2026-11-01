-- Nome legível de cada agente econômico: o grupo declarado ou, sem grupo, o provedor.
select
    agente_economico,
    min(case when grupo_economico = 'OUTROS' then nome_publico else grupo_economico end)
        as agente_nome,
    count(*) as cnpjs
from {{ ref('dim_empresa') }}
group by 1
