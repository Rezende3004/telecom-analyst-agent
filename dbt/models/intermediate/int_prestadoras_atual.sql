-- Última declaração de cada CNPJ na Anatel com cadastro preenchido. O grupo muda com o tempo,
-- e usar o atual evita que uma aquisição pareça crescimento orgânico do comprador.
select distinct on (cnpj)
    cnpj,
    empresa,
    grupo_economico,
    porte,
    mes_referencia as ultima_declaracao
from {{ ref('stg_anatel__prestadoras') }}
where empresa is not null
order by cnpj, mes_referencia desc
