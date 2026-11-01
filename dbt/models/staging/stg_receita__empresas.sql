select
    empresas.cnpj_basico,
    empresas.razao_social,
    empresas.natureza_juridica,
    naturezas.descricao as natureza_juridica_descricao,
    empresas.capital_social,
    empresas.porte_empresa
from {{ source('raw', 'empresas_receita') }} as empresas
left join {{ source('raw', 'naturezas_juridicas') }} as naturezas
    on empresas.natureza_juridica = naturezas.codigo
