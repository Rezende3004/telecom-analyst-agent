select
    make_date(ano, mes, 1) as mes_referencia,
    acessos
from {{ source('raw', 'total_mensal') }}
