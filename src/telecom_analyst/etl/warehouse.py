"""Carrega o staging no schema `raw` do Postgres, já agregado.

O DuckDB reduz as 56 milhões de linhas da Anatel à granularidade do warehouse, e cada tabela
entra pelo COPY do Postgres. O carregamento roda em uma transação: se algo falhar, o banco
continua com o snapshot anterior.
"""

import logging
import tempfile
from pathlib import Path
from typing import NamedTuple

import duckdb
import psycopg
from psycopg import sql

from telecom_analyst.config import Settings
from telecom_analyst.etl import cnpj
from telecom_analyst.etl.duck import connect
from telecom_analyst.ingest import anatel, ibge

logger = logging.getLogger(__name__)

COPY_BLOCK = 1024 * 1024
AGENT_ROLE_SETTINGS = {
    "default_transaction_read_only": "on",
    "statement_timeout": "5s",
    "search_path": "semantic",
}


class Table(NamedTuple):
    name: str
    columns: str
    query: str


def tables(acessos: Path, anatel_dir: Path, ibge_path: Path, receita_dir: Path) -> list[Table]:
    source = f"read_parquet('{acessos}/*/*.parquet', hive_partitioning = false)"
    return [
        Table(
            "acessos_mensal",
            """ano smallint, mes smallint, cnpj text, municipio_ibge text, meio_acesso text,
            tipo_pessoa text, acessos bigint""",
            f"""SELECT ano, mes, cnpj, municipio_ibge, meio_acesso,
                coalesce(tipo_pessoa, 'Não Informado') AS tipo_pessoa, sum(acessos) AS acessos
            FROM {source} GROUP BY ALL""",  # noqa: S608
        ),
        Table(
            "acessos_faixa_municipio",
            """ano smallint, mes smallint, municipio_ibge text, faixa_velocidade text,
            acessos bigint""",
            f"""SELECT ano, mes, municipio_ibge, faixa_velocidade, sum(acessos) AS acessos
            FROM {source} GROUP BY ALL""",  # noqa: S608
        ),
        Table(
            "prestadora_mensal",
            "ano smallint, mes smallint, cnpj text, empresa text, grupo_economico text, porte text",
            f"""SELECT ano, mes, cnpj, arg_max(empresa, acessos) AS empresa,
                arg_max(grupo_economico, acessos) AS grupo_economico,
                arg_max(porte, acessos) AS porte
            FROM {source} GROUP BY ALL""",  # noqa: S608
        ),
        Table(
            "total_mensal",
            "ano smallint, mes smallint, acessos bigint",
            f"SELECT * FROM read_parquet('{anatel_dir}/total_mensal.parquet')",  # noqa: S608
        ),
        Table(
            "municipios",
            """municipio_ibge text, municipio text, uf text, uf_nome text, regiao text,
            populacao bigint, populacao_ano smallint, domicilios bigint, domicilios_ano smallint,
            pib_mil_reais double precision, pib_ano smallint,
            renda_per_capita double precision, renda_ano smallint""",
            f"SELECT * FROM read_parquet('{ibge_path}')",  # noqa: S608
        ),
        Table(
            "empresas_receita",
            """cnpj_basico text, razao_social text, natureza_juridica text,
            capital_social double precision, porte_empresa text""",
            f"SELECT * FROM read_parquet('{receita_dir}/empresas.parquet')",  # noqa: S608
        ),
        Table(
            "estabelecimentos_receita",
            """cnpj text, cnpj_basico text, matriz boolean, nome_fantasia text,
            situacao_cadastral text, data_inicio_atividade date, cnae_principal text, uf text""",
            f"""SELECT cnpj, cnpj_basico, matriz, nome_fantasia, situacao_cadastral,
                data_inicio_atividade, cnae_principal, uf
            FROM read_parquet('{receita_dir}/estabelecimentos/*/*.parquet',
                              hive_partitioning = false)""",  # noqa: S608
        ),
        Table(
            "naturezas_juridicas",
            "codigo text, descricao text",
            f"SELECT * FROM read_parquet('{receita_dir}/naturezas.parquet')",  # noqa: S608
        ),
    ]


def _load(
    duck: duckdb.DuckDBPyConnection, postgres: psycopg.Connection, table: Table, workdir: Path
) -> None:
    path = workdir / f"{table.name}.csv"
    duck.execute(f"COPY ({table.query}) TO '{path}' (FORMAT csv, HEADER false)")
    with postgres.cursor() as cursor:
        cursor.execute(f"DROP TABLE IF EXISTS raw.{table.name} CASCADE")
        cursor.execute(f"CREATE TABLE raw.{table.name} ({table.columns})")
        with (
            cursor.copy(f"COPY raw.{table.name} FROM STDIN (FORMAT csv)") as copy,
            path.open("rb") as stream,
        ):
            while block := stream.read(COPY_BLOCK):
                copy.write(block)
    path.unlink()
    logger.info("raw.%s carregada", table.name)


def ensure_agent_role(postgres: psycopg.Connection, user: str, password: str) -> None:
    """Cria o usuário do agente. O dbt concede acesso só às views de `semantic`."""
    role = sql.Identifier(user)
    exists = postgres.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (user,)).fetchone()
    verb = "ALTER" if exists else "CREATE"
    postgres.execute(
        sql.SQL("{} ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD {}").format(
            sql.SQL(verb), role, sql.Literal(password)
        )
    )
    for setting, value in AGENT_ROLE_SETTINGS.items():
        postgres.execute(
            sql.SQL("ALTER ROLE {} SET {} = {}").format(
                role, sql.Identifier(setting), sql.Literal(value)
            )
        )


def load(settings: Settings, month: str, snapshot: str) -> None:
    """Carrega todas as fontes. `month` é o mês da Receita; `snapshot`, o último mês da Anatel."""
    definitions = tables(
        anatel.staging_dir(settings) / "acessos",
        anatel.staging_dir(settings),
        ibge.staging_path(settings),
        cnpj.staging_dir(settings, month),
    )
    duck = connect(settings)
    with (
        tempfile.TemporaryDirectory(dir=settings.data_dir) as workdir,
        psycopg.connect(settings.postgres_conninfo) as postgres,
    ):
        postgres.execute("CREATE SCHEMA IF NOT EXISTS raw")
        ensure_agent_role(
            postgres, settings.agent_db_user, settings.agent_db_password.get_secret_value()
        )
        for table in definitions:
            _load(duck, postgres, table, Path(workdir))
        postgres.execute("DROP TABLE IF EXISTS raw.snapshot CASCADE")
        postgres.execute("CREATE TABLE raw.snapshot (snapshot_date date, receita_mes text)")
        postgres.execute("INSERT INTO raw.snapshot VALUES (%s, %s)", (f"{snapshot}-01", month))
