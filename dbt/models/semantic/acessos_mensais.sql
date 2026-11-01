select
    acessos.mes_referencia,
    municipios.municipio,
    municipios.uf,
    municipios.regiao,
    acessos.municipio_ibge,
    acessos.cnpj,
    empresas.nome_publico as provedor,
    empresas.grupo_economico,
    empresas.agente_economico,
    agentes.agente_nome,
    acessos.meio_acesso,
    acessos.tipo_pessoa,
    acessos.acessos
from {{ ref('fato_acessos_mensal') }} as acessos
inner join {{ ref('dim_municipio') }} as municipios using (municipio_ibge)
inner join {{ ref('dim_empresa') }} as empresas using (cnpj)
inner join {{ ref('dim_agente') }} as agentes using (agente_economico)
