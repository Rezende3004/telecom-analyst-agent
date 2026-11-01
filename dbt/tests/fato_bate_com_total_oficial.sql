-- Falha para cada mês em que a soma do warehouse difere do total publicado pela Anatel.
select total.mes_referencia, total.acessos as oficial, fato.acessos as warehouse
from {{ ref('stg_anatel__total') }} as total
full join (
    select mes_referencia, sum(acessos) as acessos
    from {{ ref('fato_acessos_mensal') }}
    group by 1
) as fato using (mes_referencia)
where total.acessos is distinct from fato.acessos
