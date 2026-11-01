select distinct
    mes_referencia,
    extract(year from mes_referencia)::int as ano,
    extract(month from mes_referencia)::int as mes,
    extract(quarter from mes_referencia)::int as trimestre
from {{ ref('stg_anatel__total') }}
