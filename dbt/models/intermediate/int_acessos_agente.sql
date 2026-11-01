-- Soma por agente econômico: o grupo quando existe e, em `OUTROS`, o próprio CNPJ.
select
    acessos.mes_referencia,
    acessos.municipio_ibge,
    empresas.agente_economico,
    sum(acessos.acessos) as acessos
from {{ ref('fato_acessos_mensal') }} as acessos
inner join {{ ref('dim_empresa') }} as empresas on acessos.cnpj = empresas.cnpj
group by 1, 2, 3
