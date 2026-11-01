select
    make_date(ano, mes, 1) as mes_referencia,
    cnpj,
    empresa,
    grupo_economico,
    porte
from {{ source('raw', 'prestadora_mensal') }}
