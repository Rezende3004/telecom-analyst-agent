# ADR-001: Arquitetura geral

**Status:** aceito · **Data:** 2026-10-31

## Contexto

O projeto é um agente que responde perguntas sobre o mercado de banda larga fixa cruzando dados públicos: Anatel, Receita Federal, IBGE e normas regulatórias. Ele é mantido por uma pessoa, em meio período, e precisa rodar numa máquina só (14 GB de RAM e GPU de 6 GB) e depois numa VPS.

Três riscos orientam o desenho:

- **Texto gerado por LLM executando contra dados.** Um modelo com acesso amplo ao banco é difícil de proteger e de avaliar.
- **Resultados que mudam com os dados.** Os dados são atualizados todo mês, então uma suíte de evals sobre dados vivos mudaria sem nenhuma mudança no agente.
- **Peças demais para um projeto solo.** Cada serviço a mais precisa ser operado, protegido e explicado.

## Decisão

Separar o sistema em dois planos que só se comunicam pelo PostgreSQL.

**Plano offline.** Um job mensal baixa as fontes, transforma os dados com DuckDB e dbt, resolve entidades, analisa o grafo de sócios, treina os modelos e faz o scoring em batch. Os resultados são gravados no PostgreSQL com um snapshot por mês.

**Plano online.** O agente só lê o que o plano offline gravou, por meio de ferramentas tipadas. Ele nunca toca as tabelas diretamente:

| Ferramenta | Alcance |
| --- | --- |
| `run_sql` | só as views do schema `semantic`, com usuário somente leitura |
| `query_graph` | consultas SQL pré-definidas e parametrizadas |
| `search_regulation` | busca híbrida com re-ranking no pgvector |
| ferramentas de ML | leem scores gravados; só o KNN roda na hora, porque é leve |

As evals sempre rodam contra um snapshot congelado, e o resultado esperado vem da SQL de referência executada nesse snapshot.

### Stack de infraestrutura

- **PostgreSQL 16 + pgvector é o banco único da aplicação:** warehouse, arestas do grafo, embeddings e scores.
- **Neo4j fica fora.** As consultas de grafo do agente são poucas e previsíveis, então cabem em tabelas de arestas no Postgres, com igraph em batch. Fica como extensão opcional para exploração visual, fora do caminho crítico.
- **Spark fica fora do pipeline.** Dezenas de GB cabem no DuckDB numa máquina só. Spark entra apenas num benchmark documentado.
- **O loop do agente, os algoritmos e o harness de evals são código próprio.** É onde escrever à mão demonstra domínio. Nas outras camadas, vale a ferramenta padrão de mercado.

## Consequências

**Ganhos**

- A superfície de ataque do agente é pequena e enumerável, o que facilita o mapeamento para o OWASP LLM Top 10.
- Respostas e evals são reproduzíveis: mesmo snapshot, mesmo resultado esperado.
- A resposta online é rápida e barata, porque nenhum modelo pesado roda por pergunta.

**Custos**

- Os dados têm defasagem de até um mês, e o agente não responde sobre nada que o job mensal não tenha preparado.
- Toda pergunta nova que exija outro corte de dados depende de uma view ou de um score novo no plano offline.
- **O Langfuse self-hosted traz três serviços além do banco.** A versão 4 exige ClickHouse, Redis e armazenamento compatível com S3 (MinIO). Eles existem só para a observabilidade, então nenhum código do projeto depende deles diretamente.

### Isolamento do Langfuse

Os metadados do Langfuse ficam num banco `langfuse` separado, no mesmo servidor Postgres, sem `CONNECT` público. Assim o servidor continua um só, e os usuários do agente não alcançam os dados de observabilidade.

A versão 4 só aceita traces via OpenTelemetry (`/api/public/otel/v1/traces`) e rejeita a API de ingestão antiga. A integração do agente deve usar o SDK atual ou OTLP direto.
