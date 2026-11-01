select
    velocidade.mes_referencia,
    municipios.municipio,
    municipios.uf,
    municipios.regiao,
    velocidade.municipio_ibge,
    velocidade.faixa_velocidade,
    velocidade.acessos
from {{ ref('fato_velocidade_municipal') }} as velocidade
inner join {{ ref('dim_municipio') }} as municipios using (municipio_ibge)
