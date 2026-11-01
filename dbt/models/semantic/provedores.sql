select
    cnpj,
    nome_publico as provedor,
    grupo_economico,
    agente_economico,
    agente_nome,
    porte_prestadora,
    natureza_juridica,
    capital_social,
    uf_sede,
    data_inicio_atividade,
    situacao_cadastral
from {{ ref('dim_empresa') }}
inner join {{ ref('dim_agente') }} using (agente_economico)
