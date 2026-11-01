# DuckDB contra Spark no recorte do CNPJ

O mesmo job nos dois motores: selecionar as empresas de telecom em 24 GB de CSV, remover CPFs de nomes e gravar Parquet. Conclusão no [ADR-004](../../docs/adr/004-duckdb-em-vez-de-spark.md).

## Resultado

Base do CNPJ de 2026-10, com 73,8 milhões de estabelecimentos, em uma máquina com 16 threads e 14 GB de RAM.

| Medida | DuckDB 2.0 | PySpark 4.3, modo local |
| --- | --- | --- |
| Tempo do job | **31 s** | **246 s** |
| Pico de memória | 2,6 GB | 7,0 GB |
| Linhas de lógica | 81 | 66 |
| Estabelecimentos na saída | 694.713 | 694.713 |
| Empresas na saída | 597.401 | 597.401 |
| Sócios na saída | 202.265 | 202.265 |

- **As saídas são equivalentes.** Comparando chaves e os campos principais de estabelecimentos e empresas, não há nenhuma linha diferente.
- **O Spark escreveu menos linhas.** A API de DataFrame ficou mais curta que o SQL com as views.
- **Rodadas do Spark:** 249,7 s e 246,0 s. A memória é o pico da JVM, amostrado a cada segundo, com `spark.driver.memory` em 6 GB.

## Limites

- É uma máquina só, que é o cenário oposto ao que justifica o Spark.
- O DuckDB tem uma rodada limpa e o Spark, duas.
- A extração de CSV (251 s, em comum) fica fora da conta, e os arquivos já estavam em cache de disco.

## Como reproduzir

```bash
make ingest
uv run python -c "from telecom_analyst.config import load_settings; from telecom_analyst.etl import cnpj; cnpj.extract_csvs(load_settings(), '2026-10')"

CSV=data/staging/receita/2026-10.csv
ANATEL=data/staging/anatel/acessos
uv run python benchmarks/duckdb_vs_spark/duckdb_job.py $CSV $ANATEL /tmp/saida_duckdb
uv run --group benchmark python benchmarks/duckdb_vs_spark/spark_job.py $CSV $ANATEL /tmp/saida_spark
```

O Spark exige Java 17 ou mais recente.
