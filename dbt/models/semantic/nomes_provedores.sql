select distinct
    nomes.nome,
    agentes.agente_nome,
    agentes.agente_economico,
    agentes.acessos_atuais
from {{ ref('int_nomes_prestadora') }} as nomes
inner join {{ ref('dim_empresa') }} as empresas using (cnpj)
inner join {{ ref('dim_agente') }} as agentes using (agente_economico)
