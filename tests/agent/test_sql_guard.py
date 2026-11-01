import pytest

from telecom_analyst.agent.guardrails.sql import MAX_LIMIT, UnsafeSqlError, validate_sql


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT uf, sum(acessos) FROM semantic.acessos_mensais GROUP BY uf",
        "SELECT municipio FROM mercado_municipal",
        "WITH base AS (SELECT uf FROM semantic.municipios) SELECT * FROM base",
        "SELECT uf FROM semantic.municipios UNION SELECT uf FROM semantic.provedores",
        "SELECT rank() OVER (ORDER BY acessos DESC) FROM semantic.mercado_municipal",
        "SELECT a.uf FROM semantic.municipios a JOIN semantic.provedores b ON a.uf = b.uf_sede",
        "SELECT round(avg(hhi), 2) FROM semantic.mercado_municipal GROUP BY uf",
        "SELECT date_trunc('year', mes_referencia) FROM semantic.mercado_municipal",
    ],
)
def test_accepts_read_queries(sql: str) -> None:
    assert "LIMIT" in validate_sql(sql)


@pytest.mark.parametrize(
    ("sql", "reason"),
    [
        ("DROP TABLE semantic.municipios", "só SELECT"),
        ("DELETE FROM semantic.municipios", "só SELECT"),
        ("UPDATE semantic.municipios SET uf = 'X'", "só SELECT"),
        ("INSERT INTO semantic.municipios VALUES (1)", "só SELECT"),
        ("TRUNCATE semantic.municipios", "só SELECT"),
        ("CREATE TABLE x AS SELECT 1", "só SELECT"),
        ("ALTER ROLE agent_ro SUPERUSER", "só SELECT"),
        ("GRANT ALL ON marts.dim_empresa TO agent_ro", "só SELECT"),
        ("COPY semantic.municipios TO '/tmp/x'", "só SELECT"),
        ("SET statement_timeout = 0", "só SELECT"),
        ("SELECT 1; DROP TABLE semantic.municipios", "exatamente uma"),
        ("SELECT * INTO copia FROM semantic.municipios", "só SELECT"),
        ("WITH x AS (DELETE FROM semantic.municipios RETURNING *) SELECT * FROM x", "só SELECT"),
        ("SELECT * FROM semantic.municipios FOR UPDATE", "só SELECT"),
        ("SELECT * FROM marts.dim_empresa", "tabela não permitida"),
        ("SELECT * FROM raw.empresas_receita", "tabela não permitida"),
        ("SELECT * FROM pg_catalog.pg_user", "tabela não permitida"),
        ("SELECT * FROM pg_shadow", "tabela não permitida"),
        ("SELECT * FROM information_schema.tables", "tabela não permitida"),
        ("SELECT * FROM outro.semantic.municipios", "tabela não permitida"),
        ("SELECT * FROM semantic.municipios m, marts.dim_empresa d", "tabela não permitida"),
        ("SELECT (SELECT count(*) FROM raw.total_mensal)", "tabela não permitida"),
        ("WITH x AS (SELECT * FROM marts.dim_empresa) SELECT * FROM x", "tabela não permitida"),
        ("SELECT pg_sleep(10)", "função não permitida"),
        ("SELECT pg_read_file('/etc/passwd')", "função não permitida"),
        ("SELECT current_setting('server_version')", "função não permitida"),
        ("SELECT set_config('statement_timeout', '0', false)", "função não permitida"),
        ("SELECT lo_import('/etc/passwd')", "função não permitida"),
        ("SELECT dblink_connect('host=x')", "função não permitida"),
        ("SELEC uf FROM semantic.municipios", "SQL inválida"),
    ],
)
def test_rejects_unsafe_queries(sql: str, reason: str) -> None:
    with pytest.raises(UnsafeSqlError, match=reason):
        validate_sql(sql)


def test_rejects_empty_input() -> None:
    with pytest.raises(UnsafeSqlError):
        validate_sql("   ")


def test_adds_limit_when_missing() -> None:
    assert validate_sql("SELECT uf FROM semantic.municipios").endswith("LIMIT 100")


def test_keeps_smaller_limit() -> None:
    assert validate_sql("SELECT uf FROM semantic.municipios LIMIT 5").endswith("LIMIT 5")


def test_caps_large_limit() -> None:
    query = validate_sql("SELECT uf FROM semantic.municipios LIMIT 1000000")

    assert query.endswith(f"LIMIT {MAX_LIMIT}")


def test_rejects_non_numeric_limit() -> None:
    with pytest.raises(UnsafeSqlError, match="LIMIT"):
        validate_sql("SELECT uf FROM semantic.municipios LIMIT (SELECT 1)")
