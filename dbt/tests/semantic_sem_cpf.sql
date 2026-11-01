-- O agente é público: nenhum nome exposto pode conter um número no formato de CPF.
select cnpj, provedor
from {{ ref('provedores') }}
where provedor ~ '[0-9]{11}'
