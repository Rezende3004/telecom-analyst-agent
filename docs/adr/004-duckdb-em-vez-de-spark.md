# ADR-004: DuckDB em vez de Spark no pipeline

**Status:** aceito · **Data:** 2026-10-31

## Contexto

O ADR-001 afirmou que a base do CNPJ cabe numa máquina só e que Spark entraria apenas num benchmark. Essa afirmação precisava de números.

## Decisão

Manter o DuckDB no pipeline. No recorte de 24 GB do CNPJ, o [benchmark](../../benchmarks/duckdb_vs_spark/README.md) mediu:

| Medida | DuckDB | PySpark local |
| --- | --- | --- |
| Tempo | 31 s | 246 s |
| Pico de memória | 2,6 GB | 7,0 GB |
| Saída | idêntica | idêntica |

O job roda uma vez por mês, numa máquina só, e cabe na memória disponível com folga. O Spark custaria 8 vezes mais tempo, quase 3 vezes mais memória e uma dependência de Java.

## Consequências

- O pipeline fica preso a uma máquina. Isso é aceitável enquanto os dados crescerem devagar: a base do CNPJ e a série da Anatel ganham uma fração pequena por mês.
- O Spark passaria a valer a pena com dados que não coubessem em uma máquina ou com um cluster já disponível. Nenhum dos dois casos existe aqui.
- O benchmark fica no repositório e não entra no pipeline. PySpark é um grupo de dependências opcional.
