select mes_referencia, municipio_ibge, sum(market_share_pct) as soma
from {{ ref('fato_participacao_agente') }}
group by 1, 2
having abs(sum(market_share_pct) - 100) > 0.0001
