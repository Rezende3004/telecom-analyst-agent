select
    cnpj,
    cnpj_basico,
    matriz,
    nullif(trim(nome_fantasia), '') as nome_fantasia,
    case situacao_cadastral
        when '01' then 'Nula'
        when '02' then 'Ativa'
        when '03' then 'Suspensa'
        when '04' then 'Inapta'
        when '08' then 'Baixada'
    end as situacao_cadastral,
    data_inicio_atividade,
    cnae_principal,
    uf
from {{ source('raw', 'estabelecimentos_receita') }}
