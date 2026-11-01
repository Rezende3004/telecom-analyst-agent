select
    make_date(ano, mes, 1) as mes_referencia,
    cnpj,
    municipio_ibge,
    meio_acesso,
    tipo_pessoa,
    acessos
from {{ source('raw', 'acessos_mensal') }}
