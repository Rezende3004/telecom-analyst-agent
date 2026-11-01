select
    municipio_ibge,
    municipio,
    uf,
    uf_nome,
    regiao,
    populacao,
    populacao_ano,
    domicilios,
    domicilios_ano,
    pib_mil_reais,
    pib_ano,
    renda_per_capita,
    renda_ano
from {{ ref('stg_ibge__municipios') }}
