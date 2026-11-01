-- A Anatel repete o CPF que a Receita embute no nome de MEIs: ele não passa daqui.
select
    make_date(ano, mes, 1) as mes_referencia,
    cnpj,
    nullif(trim(regexp_replace(empresa, '[0-9]{11}', '', 'g')), '') as empresa,
    grupo_economico,
    porte
from {{ source('raw', 'prestadora_mensal') }}
