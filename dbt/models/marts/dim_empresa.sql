-- Empresário individual (natureza 2135) usa o nome civil como razão social, e o nome na Anatel
-- costuma repeti-lo. A demo pública não mostra nomes de pessoas, então `nome_publico` recorre
-- ao nome fantasia, quando ele não repete a razão social, ou ao CNPJ. Nos demais casos vale o
-- nome comercial declarado à Anatel.
with sede as (
    select distinct on (cnpj_basico)
        cnpj_basico,
        uf,
        data_inicio_atividade,
        situacao_cadastral,
        nome_fantasia
    from {{ ref('stg_receita__estabelecimentos') }}
    order by cnpj_basico, matriz desc, data_inicio_atividade
)

select
    prestadoras.cnpj,
    left(prestadoras.cnpj, 8) as cnpj_basico,
    case
        when empresas.natureza_juridica = '2135'
            then coalesce(
                case
                    when upper(sede.nome_fantasia) <> upper(empresas.razao_social)
                        then sede.nome_fantasia
                end,
                'Empresário individual ' || left(prestadoras.cnpj, 8)
            )
        else coalesce(prestadoras.empresa, empresas.razao_social)
    end as nome_publico,
    coalesce(prestadoras.grupo_economico, 'OUTROS') as grupo_economico,
    case
        when coalesce(prestadoras.grupo_economico, 'OUTROS') = 'OUTROS'
            then left(prestadoras.cnpj, 8)
        else prestadoras.grupo_economico
    end as agente_economico,
    prestadoras.porte as porte_prestadora,
    coalesce(empresas.natureza_juridica = '2135', false) as empresario_individual,
    empresas.razao_social,
    case
        when upper(sede.nome_fantasia) = upper(empresas.razao_social)
            and empresas.natureza_juridica = '2135'
            then null
        else sede.nome_fantasia
    end as nome_fantasia,
    empresas.natureza_juridica_descricao as natureza_juridica,
    empresas.capital_social,
    sede.uf as uf_sede,
    sede.data_inicio_atividade,
    sede.situacao_cadastral,
    prestadoras.ultima_declaracao,
    empresas.cnpj_basico is not null as encontrado_na_receita
from {{ ref('int_prestadoras_atual') }} as prestadoras
left join {{ ref('stg_receita__empresas') }} as empresas
    on left(prestadoras.cnpj, 8) = empresas.cnpj_basico
left join sede on left(prestadoras.cnpj, 8) = sede.cnpj_basico
