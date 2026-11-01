"""Conexão DuckDB com os limites de memória do projeto."""

import duckdb

from telecom_analyst.config import Settings


def connect(settings: Settings) -> duckdb.DuckDBPyConnection:
    spill = settings.data_dir / ".duckdb_tmp"
    spill.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect()
    connection.execute(f"SET memory_limit = '{settings.duckdb_memory_limit}'")
    connection.execute(f"SET temp_directory = '{spill}'")
    return connection
