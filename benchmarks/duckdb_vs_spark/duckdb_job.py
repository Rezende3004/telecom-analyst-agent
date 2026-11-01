"""Recorte de telecom da base do CNPJ com DuckDB. Reutiliza o job de produção."""

import json
import shutil
import sys
import time
from pathlib import Path

from telecom_analyst.config import load_settings
from telecom_analyst.etl import cnpj
from telecom_analyst.etl.duck import connect


def main(csvs: Path, providers: Path, output: Path) -> None:
    shutil.rmtree(output, ignore_errors=True)
    output.mkdir(parents=True)
    connection = connect(load_settings())
    started = time.perf_counter()
    cnpj.build_views(connection, csvs, providers)
    cnpj.write_tables(connection, csvs, output)
    elapsed = time.perf_counter() - started

    rows = {
        table: connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]  # noqa: S608
        for table in ("estabelecimentos", "empresas", "socios")
    }
    print(json.dumps({"engine": "duckdb", "seconds": round(elapsed, 1), "rows": rows}))


if __name__ == "__main__":
    main(*(Path(argument) for argument in sys.argv[1:4]))
