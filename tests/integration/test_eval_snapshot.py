import gzip
import hashlib
import json
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from evals import snapshot
from psycopg import errors, sql
from psycopg.conninfo import make_conninfo

from telecom_analyst.config import Settings, load_settings

pytestmark = pytest.mark.integration

DATABASE = "eval_snapshot_test"


def write_snapshot(directory: Path) -> None:
    content = gzip.compress(b"5201108,10\n5208707,20\n")
    (directory / "dados.csv.gz").write_bytes(content)
    manifest = {
        "dados": {
            "columns": [["municipio_ibge", "text"], ["acessos", "bigint"]],
            "rows": 2,
            "sha256": hashlib.sha256(content).hexdigest(),
        }
    }
    (directory / "manifest.json").write_text(json.dumps(manifest))


@pytest.fixture
def settings() -> Iterator[Settings]:
    current = load_settings()
    yield current
    with psycopg.connect(current.postgres_conninfo, autocommit=True) as admin:
        admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(DATABASE)))


def test_load_creates_tables_readable_by_the_agent(settings: Settings, tmp_path: Path) -> None:
    write_snapshot(tmp_path)

    snapshot.load(settings, tmp_path, DATABASE)

    conninfo = make_conninfo(settings.agent_conninfo, dbname=DATABASE)
    with psycopg.connect(conninfo) as connection:
        row = connection.execute("SELECT sum(acessos) FROM semantic.dados").fetchone()
    assert row == (30,)


def test_agent_stays_read_only_on_the_snapshot(settings: Settings, tmp_path: Path) -> None:
    write_snapshot(tmp_path)
    snapshot.load(settings, tmp_path, DATABASE)

    conninfo = make_conninfo(settings.agent_conninfo, dbname=DATABASE)
    with psycopg.connect(conninfo) as connection, pytest.raises(errors.ReadOnlySqlTransaction):
        connection.execute("DELETE FROM semantic.dados")


def test_refuses_to_replace_the_main_database(settings: Settings, tmp_path: Path) -> None:
    write_snapshot(tmp_path)

    with pytest.raises(ValueError, match="banco principal"):
        snapshot.load(settings, tmp_path, settings.postgres_db)


def test_rejects_tampered_file(settings: Settings, tmp_path: Path) -> None:
    write_snapshot(tmp_path)
    (tmp_path / "dados.csv.gz").write_bytes(gzip.compress(b"5201108,999999\n"))

    with pytest.raises(ValueError, match="checksum"):
        snapshot.load(settings, tmp_path, DATABASE)
