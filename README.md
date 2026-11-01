# Analista de Mercado Telecom

Agente de IA que responde, em português, perguntas analíticas sobre o mercado brasileiro de banda larga fixa, usando só dados públicos e mostrando de onde saiu cada número.

> **Em construção.** O pipeline de dados e o warehouse já funcionam com dados reais até 2026-09. O agente ainda não existe: as seções sobre ele descrevem o que está planejado.

## O problema

Os dados do setor são públicos, mas estão espalhados: acessos por município na Anatel, quadro societário na Receita Federal, população e renda no IBGE, obrigações em resoluções da Anatel. Responder uma pergunta de mercado exige cruzar tudo isso à mão.

O sistema deve responder perguntas como:

- Quais cidades de Goiás com mais de 50 mil habitantes têm mercado pouco disputado?
- Quais grupos econômicos de provedores mais cresceram no Centro-Oeste desde 2022?
- Quanto o provedor X deve crescer em Anápolis nos próximos 12 meses?
- O que a regulação exige de um provedor de pequeno porte em relação ao atendimento?

## O que já funciona

- **56,2 milhões de linhas** da Anatel, com os 205 meses idênticos ao total oficial publicado.
- **24 GB da base do CNPJ** reduzidos ao recorte de telecom em 31 segundos depois de descompactados, sem CPFs nem contatos. O [benchmark](benchmarks/duckdb_vs_spark/README.md) mostra o DuckDB 8 vezes mais rápido que o Spark nesse job.
- **100% dos CNPJs da Anatel** ligados à Receita pela chave exata.
- **Warehouse dbt** com 51 modelos e testes, incluindo a conciliação com o total oficial e o bloqueio de CPF nos dados expostos.

Ao longo do caminho, os dados mostraram que a densidade publicada pela Anatel usa população, embora a metodologia diga domicílios. Esse e outros achados estão em [Fontes de dados](docs/data-sources.md), e as colunas em [Dicionário de dados](docs/data-dictionary.md).

## Arquitetura planejada

Um plano offline prepara tudo uma vez por mês e um plano online só consulta. O agente nunca toca os dados diretamente: tudo passa por ferramentas tipadas, o que torna o sistema seguro, testável e avaliável. A justificativa está no [ADR-001](docs/adr/001-arquitetura-geral.md).

```mermaid
flowchart TB
    subgraph offline["Plano offline · job mensal no Prefect"]
        fontes["Anatel · Receita · IBGE · Normas"] --> etl["DuckDB · dbt · resolução de entidades · grafo"]
        etl --> treino["Treino e scoring · MLflow"]
    end

    pg[("PostgreSQL + pgvector<br/>snapshot versionado por mês")]
    etl --> pg
    treino --> pg

    subgraph online["Plano online"]
        tools["run_sql · query_graph · search_regulation · ferramentas de ML"]
        agente["Agente: planeja → chama ferramenta → verifica → responde"]
        llm["Roteador: modelo local ou API"]
        app["FastAPI + Streamlit"]
        app --> agente
        agente --> tools
        agente <--> llm
    end

    tools --> pg
    agente -.-> langfuse["Langfuse · traces e custo"]
    langfuse -.->|falhas viram casos novos| evals["Evals no CI · snapshot congelado"]
```

## Como rodar

Requer [uv](https://docs.astral.sh/uv/), Docker com Compose e make.

```bash
make setup   # dependências, .env e pre-commit
make up      # sobe a stack e espera ficar saudável
make test    # testes unitários e de integração
```

Para montar o warehouse com os dados públicos, que baixam cerca de 8 GB:

```bash
make ingest     # Anatel e IBGE
make cnpj       # base do CNPJ
make transform  # carrega o Postgres e roda o dbt
make snapshot   # congela a versão atual
```

| Serviço | Endereço local |
| --- | --- |
| PostgreSQL + pgvector | `localhost:5433` |
| MLflow | <http://localhost:5000> |
| Langfuse | <http://localhost:3001> (credenciais de admin no `.env`) |

As portas ficam presas a `127.0.0.1` e podem ser trocadas no `.env`. `make help` lista todos os alvos.

## Roteiro

| Fase | Entrega | Situação |
| --- | --- | --- |
| 0 | Fundação: repositório, stack local e CI | concluída |
| 1 | Warehouse, agente text-to-SQL e evals | em andamento: dados e warehouse prontos |
| 2 | Grafo de sócios e RAG regulatório | planejada |
| 3 | Fine-tuning de modelo pequeno para text-to-SQL | planejada |
| 4 | Ferramentas de ML, segurança, observabilidade e deploy | planejada |
