-- Empresário individual (natureza 2135) usa o nome civil como razão social. A demo pública
-- não mostra nomes de pessoas, então `nome_publico` recorre ao nome fantasia ou ao CNPJ.
with sede as (
    select distinct on (cnpj_basico)
        cnpj_basico,
        uf,
        data_inicio_atividade,
        situacao_cadastral,
        nome_fantasia
    from {{ ref('stg_receita__estabelecimentos') }}
    order by cnpj_basico, matriz desc, data_inicio_atividade
),

cadastro as (
    select distinct on (prestadoras.cnpj)
        prestadoras.cnpj,
        left(prestadoras.cnpj, 8) as cnpj_basico,
        prestadoras.empresa,
        coalesce(prestadoras.grupo_economico, 'OUTROS') as grupo_economico,
        prestadoras.porte,
        prestadoras.ultima_declaracao
    from {{ ref('int_prestadoras_atual') }} as prestadoras
    order by prestadoras.cnpj
)

select
    cadastro.cnpj,
    cadastro.cnpj_basico,
    case
        when empresas.natureza_juridica = '2135'
            then coalesce(sede.nome_fantasia, 'Empresário individual ' || cadastro.cnpj_basico)
        else coalesce(empresas.razao_social, cadastro.empresa)
    end as nome_publico,
    cadastro.grupo_economico,
    case
        when cadastro.grupo_economico = 'OUTROS' then cadastro.cnpj_basico
        else cadastro.grupo_economico
    end as agente_economico,
    cadastro.porte as porte_prestadora,
    empresas.natureza_juridica_descricao as natureza_juridica,
    empresas.capital_social,
    sede.uf as uf_sede,
    sede.data_inicio_atividade,
    sede.situacao_cadastral,
    cadastro.ultima_declaracao,
    empresas.cnpj_basico is not null as encontrado_na_receita
from cadastro
left join {{ ref('stg_receita__empresas') }} as empresas
    on cadastro.cnpj_basico = empresas.cnpj_basico
left join sede on cadastro.cnpj_basico = sede.cnpj_basico
