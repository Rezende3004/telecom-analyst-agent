select
    make_date(ano, mes, 1) as mes_referencia,
    municipio_ibge,
    faixa_velocidade,
    acessos
from {{ source('raw', 'acessos_faixa_municipio') }}
