select nome
from {{ ref('nomes_provedores') }}
where nome ~ '[0-9]{11}'
