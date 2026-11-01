"""Snapshot reduzido para as evals: só os dados que as perguntas golden precisam.

    python -m evals.snapshot export data/snapshots/evals-2026-09
    python -m evals.snapshot load data/snapshots/evals-2026-09 telecom_eval

Fica de fora a view `provedores`, que traz capital social e não é usada pelas perguntas.
Grava cada view como CSV comprimido, com um manifesto de colunas, linhas e checksums. Ao
carregar, as views viram tabelas no schema `semantic`, com os mesmos nomes, e o agente roda sem
mudar nada. Os dados são reais, então nada daqui entra no git.
"""

import argparse
import gzip
import hashlib
import json
from pathlib import Path

import psycopg
from psycopg import sql

from telecom_analyst.config import Settings, load_settings
from telecom_analyst.etl.warehouse import ensure_agent_role

COPY_BLOCK = 1024 * 1024
RECENT_MONTHS = "mes_referencia IN ('2023-09-01', '2025-09-01', '2026-09-01')"
FILTERS: dict[str, str | None] = {
    "snapshot": None,
    "municipios": None,
    "nomes_provedores": None,
    "mercado_municipal": None,
    "participacao_provedores": RECENT_MONTHS,
    "acessos_mensais": "mes_referencia IN ('2021-12-01', '2022-01-01', '2026-09-01')",
    "velocidade_municipal": "mes_referencia = '2026-09-01'",
}
NAME_COLUMNS = ("nome", "agente_nome", "provedor", "lider")


class UnsafeSnapshotError(ValueError):
    """Um nome do snapshot tem formato de CPF."""


def _columns(connection: psycopg.Connection, view: str) -> list[tuple[str, str]]:
    query = """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'semantic' AND table_name = %s
        ORDER BY ordinal_position
    """
    rows = connection.execute(query, (view,)).fetchall()
    return [(str(name), str(kind)) for name, kind in rows]


def _selection(view: str) -> sql.Composable:
    query = sql.SQL("SELECT * FROM semantic.{}").format(sql.Identifier(view))
    condition = FILTERS[view]
    return query if condition is None else query + sql.SQL(" WHERE " + condition)


def _check_names(connection: psycopg.Connection, view: str, columns: list[str]) -> None:
    for column in set(columns) & set(NAME_COLUMNS):
        query = sql.SQL("SELECT count(*) FROM semantic.{} WHERE {} ~ '[0-9]{{11}}'").format(
            sql.Identifier(view), sql.Identifier(column)
        )
        row = connection.execute(query).fetchone()
        if row is not None and row[0]:
            raise UnsafeSnapshotError(f"{view}.{column}: {row[0]} nomes com formato de CPF")


def export(settings: Settings, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, dict[str, object]] = {}
    with psycopg.connect(settings.postgres_conninfo) as connection, connection.cursor() as cursor:
        for view in FILTERS:
            columns = _columns(connection, view)
            _check_names(connection, view, [name for name, _ in columns])
            target = directory / f"{view}.csv.gz"
            rows = 0
            copy = sql.SQL("COPY ({}) TO STDOUT (FORMAT csv)").format(_selection(view))
            with cursor.copy(copy) as stream, gzip.open(target, "wb") as output:
                for block in stream:
                    output.write(block)
                    rows += bytes(block).count(b"\n")
            manifest[view] = {
                "columns": columns,
                "rows": rows,
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            }
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))


def _create_database(settings: Settings, database: str) -> None:
    name = sql.Identifier(database)
    with psycopg.connect(settings.postgres_conninfo, autocommit=True) as admin:
        admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(name))
        admin.execute(sql.SQL("CREATE DATABASE {}").format(name))


def load(settings: Settings, directory: Path, database: str) -> None:
    """Recria `database` a partir do snapshot. Nunca toca no banco principal."""
    if database == settings.postgres_db:
        raise ValueError("o snapshot não pode substituir o banco principal")
    manifest = json.loads((directory / "manifest.json").read_text())
    _create_database(settings, database)
    conninfo = psycopg.conninfo.make_conninfo(settings.postgres_conninfo, dbname=database)
    role = sql.Identifier(settings.agent_db_user)
    with psycopg.connect(conninfo) as connection, connection.cursor() as cursor:
        ensure_agent_role(
            connection, settings.agent_db_user, settings.agent_db_password.get_secret_value()
        )
        cursor.execute("CREATE SCHEMA semantic")
        cursor.execute(sql.SQL("GRANT USAGE ON SCHEMA semantic TO {}").format(role))
        for view, entry in manifest.items():
            source = directory / f"{view}.csv.gz"
            if hashlib.sha256(source.read_bytes()).hexdigest() != entry["sha256"]:
                raise ValueError(f"{source.name}: checksum diferente do manifesto")
            table = sql.Identifier("semantic", view)
            columns = sql.SQL(", ").join(
                sql.SQL("{} {}").format(sql.Identifier(name), sql.SQL(kind))
                for name, kind in entry["columns"]
            )
            cursor.execute(sql.SQL("CREATE TABLE {} ({})").format(table, columns))
            copy = sql.SQL("COPY {} FROM STDIN (FORMAT csv)").format(table)
            with cursor.copy(copy) as stream, gzip.open(source, "rb") as data:
                while block := data.read(COPY_BLOCK):
                    stream.write(block)
            cursor.execute(sql.SQL("GRANT SELECT ON {} TO {}").format(table, role))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["export", "load"])
    parser.add_argument("directory", type=Path)
    parser.add_argument("database", nargs="?", default="telecom_eval")
    arguments = parser.parse_args()
    settings = load_settings()
    if arguments.action == "export":
        export(settings, arguments.directory)
    else:
        load(settings, arguments.directory, arguments.database)


if __name__ == "__main__":
    main()
