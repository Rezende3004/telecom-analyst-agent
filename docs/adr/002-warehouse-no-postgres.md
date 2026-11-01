# ADR-002: dbt no Postgres sobre dados já agregados

**Status:** aceito · **Data:** 2026-10-31

## Contexto

O diagrama da arquitetura mostra DuckDB e dbt juntos no plano offline, com o resultado carregado no Postgres. Ao implementar, surgiram duas perguntas: em qual banco o dbt roda e em qual granularidade a tabela fato fica. A série da Anatel tem 56 milhões de linhas, e o Postgres precisa caber numa VPS pequena.

Linhas por granularidade, medidas em 2026-09:

| Granularidade | Linhas |
| --- | --- |
| todas as dimensões | 54,0 milhões |
| sem velocidade numérica | 32,5 milhões |
| mês, CNPJ, município, meio e faixa e tipo de pessoa | 28,8 milhões |
| **mês, CNPJ, município, meio e tipo de pessoa** | **16,1 milhões** |
| mês, CNPJ e município | 9,7 milhões |

## Decisão

- **O DuckDB agrega e o dbt roda no Postgres.** As views do schema `semantic` precisam existir no banco que o agente consulta. Com dbt em DuckDB, a camada semântica ficaria fora do projeto dbt ou exigiria dois projetos.
- **A tabela fato tem 16,1 milhões de linhas.** Tecnologia sai porque os nomes mudam ao longo da série. Velocidade numérica sai porque tem erros de declaração. Faixa de velocidade vai para `fato_velocidade_municipal`, agregada por município, o suficiente para as perguntas do plano.
- **O snapshot é um `pg_dump` de `marts` e `semantic`.** Repetir as linhas a cada mês com uma coluna `snapshot_date` faria o banco crescer sem limite. O Postgres guarda a versão atual, identificada em `semantic.snapshot`, e `make snapshot` congela um arquivo restaurável com checksum, usado nas evals.
- **O market share é calculado por agente econômico.** O agente é o grupo declarado à Anatel ou, em `OUTROS`, a raiz do CNPJ. Tratar `OUTROS` como uma empresa só inventaria um provedor com 40% do Brasil.
- **O grupo é o mais recente, aplicado a toda a série.** Com o grupo da época, cada aquisição pareceria crescimento orgânico do comprador.
- **Os limites de concentração vêm do Guia H do CADE (2016):** não concentrado abaixo de 1.500, moderadamente concentrado de 1.500 a 2.500 e altamente concentrado acima de 2.500.

## Consequências

- Uma pergunta por tecnologia específica, como FTTH contra HFC, não é respondida no warehouse. Só `meio_acesso` está disponível.
- O histórico de um grupo inclui as empresas que ele comprou, como se sempre fossem dele. Assim, uma aquisição não aparece como salto de acessos no mês da compra.
- O HHI do CADE supõe um mercado relevante definido. Tratar cada município como um mercado é uma aproximação, e o grupo `OUTROS` só será resolvido na Fase 2.
