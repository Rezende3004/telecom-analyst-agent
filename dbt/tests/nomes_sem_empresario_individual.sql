-- Razão social de empresário individual é nome civil e não pode ser pesquisável.
select empresas.razao_social
from {{ ref('dim_empresa') }} as empresas
inner join {{ ref('nomes_provedores') }} as nomes on empresas.razao_social = nomes.nome
where empresas.empresario_individual
