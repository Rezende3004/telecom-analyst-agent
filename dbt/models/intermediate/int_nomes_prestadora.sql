-- Todo nome pelo qual um CNPJ já foi conhecido. Empresário individual fica só com o nome público.
with nomes as (
    select cnpj, nome_publico as nome from {{ ref('dim_empresa') }}
    union
    select cnpj, grupo_economico from {{ ref('dim_empresa') }}
    where grupo_economico <> 'OUTROS'
    union
    select cnpj, razao_social from {{ ref('dim_empresa') }}
    where not empresario_individual
    union
    select cnpj, nome_fantasia from {{ ref('dim_empresa') }}
    union
    select declaracoes.cnpj, declaracoes.empresa
    from {{ ref('stg_anatel__prestadoras') }} as declaracoes
    inner join {{ ref('dim_empresa') }} as empresas using (cnpj)
    where not empresas.empresario_individual
)

-- A Anatel às vezes usa o nome civil de um empresário individual em declarações de outro CNPJ.
select distinct cnpj, nome
from nomes
where nome is not null
    and nome not in (
        select razao_social
        from {{ ref('dim_empresa') }}
        where empresario_individual and razao_social is not null
    )
