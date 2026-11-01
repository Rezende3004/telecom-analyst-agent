"""Segunda barreira: mesmo sem o validador de SQL, o usuário do agente só lê o semantic."""

from collections.abc import Iterator

import psycopg
import pytest
from psycopg import errors, sql
from psycopg.conninfo import make_conninfo

from telecom_analyst.config import Settings, load_settings
from telecom_analyst.etl.warehouse import ensure_agent_role

pytestmark = pytest.mark.integration

DATABASE = "agent_role_test"
ROLE = "agent_role_test_user"
PASSWORD = "test-password"  # noqa: S105


def drop_everything(admin: psycopg.Connection) -> None:
    admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(DATABASE)))
    admin.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(ROLE)))


def setup_database(settings: Settings) -> None:
    with psycopg.connect(make_conninfo(settings.postgres_conninfo, dbname=DATABASE)) as owner:
        ensure_agent_role(owner, ROLE, PASSWORD)
        owner.execute("CREATE SCHEMA marts")
        owner.execute("CREATE SCHEMA semantic")
        owner.execute("CREATE TABLE marts.dados (valor int)")
        owner.execute("INSERT INTO marts.dados VALUES (42)")
        owner.execute("CREATE VIEW semantic.dados AS SELECT valor FROM marts.dados")
        owner.execute(sql.SQL("GRANT USAGE ON SCHEMA semantic TO {}").format(sql.Identifier(ROLE)))
        owner.execute(sql.SQL("GRANT SELECT ON semantic.dados TO {}").format(sql.Identifier(ROLE)))


@pytest.fixture(scope="module")
def conninfo() -> Iterator[str]:
    settings = load_settings()
    with psycopg.connect(settings.postgres_conninfo, autocommit=True) as admin:
        drop_everything(admin)
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(DATABASE)))
    setup_database(settings)
    yield make_conninfo(settings.postgres_conninfo, dbname=DATABASE, user=ROLE, password=PASSWORD)
    with psycopg.connect(settings.postgres_conninfo, autocommit=True) as admin:
        drop_everything(admin)


def test_reads_semantic_views(conninfo: str) -> None:
    with psycopg.connect(conninfo) as connection:
        assert connection.execute("SELECT valor FROM dados").fetchone() == (42,)


def test_cannot_read_tables_behind_the_view(conninfo: str) -> None:
    with psycopg.connect(conninfo) as connection, pytest.raises(errors.InsufficientPrivilege):
        connection.execute("SELECT * FROM marts.dados")


def test_has_no_write_permission(conninfo: str) -> None:
    with psycopg.connect(conninfo) as connection, pytest.raises(errors.InsufficientPrivilege):
        connection.execute("DELETE FROM semantic.dados")


@pytest.mark.parametrize(
    "statement", ["CREATE TABLE semantic.nova (x int)", "CREATE TEMP TABLE nova (x int)"]
)
def test_transaction_is_read_only(conninfo: str, statement: str) -> None:
    with psycopg.connect(conninfo) as connection, pytest.raises(errors.ReadOnlySqlTransaction):
        connection.execute(statement)


def test_long_query_is_cancelled(conninfo: str) -> None:
    with psycopg.connect(conninfo) as connection, pytest.raises(errors.QueryCanceled):
        connection.execute("SELECT pg_sleep(6)")
