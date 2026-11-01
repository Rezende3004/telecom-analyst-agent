"""Validação da SQL escrita pelo modelo, antes de qualquer contato com o banco.

É a primeira de duas barreiras. A segunda é o usuário `agent_ro`: mesmo que esta validação
falhe, ele só lê o schema `semantic`, em transação somente leitura e com timeout.
"""

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

SEMANTIC_SCHEMA = "semantic"
ALLOWED_VIEWS = frozenset(
    {
        "acessos_mensais",
        "mercado_municipal",
        "municipios",
        "nomes_provedores",
        "participacao_provedores",
        "provedores",
        "snapshot",
        "velocidade_municipal",
    }
)
DEFAULT_LIMIT = 100
MAX_LIMIT = 500

FORBIDDEN_NODES = (
    exp.Alter,
    exp.Command,
    exp.Copy,
    exp.Create,
    exp.Delete,
    exp.Drop,
    exp.Grant,
    exp.Insert,
    exp.Into,
    exp.Lock,
    exp.Merge,
    exp.Set,
    exp.TruncateTable,
    exp.Update,
)
FORBIDDEN_FUNCTION_PREFIXES = ("pg_", "lo_", "dblink", "query_to_xml", "table_to_xml")
FORBIDDEN_FUNCTIONS = frozenset(
    {"current_setting", "set_config", "version", "inet_server_addr", "database_to_xml"}
)


class UnsafeSqlError(ValueError):
    """A SQL foi recusada. A mensagem volta ao modelo para ele corrigir a consulta."""


def _check_tables(tree: exp.Expr) -> None:
    cte_names = {cte.alias_or_name for cte in tree.find_all(exp.CTE)}
    for table in tree.find_all(exp.Table):
        if not table.name:
            raise UnsafeSqlError("só é permitido consultar views do schema semantic")
        if table.name in cte_names and not table.db:
            continue
        schema_ok = table.db in ("", SEMANTIC_SCHEMA) and not table.catalog
        if not schema_ok or table.name not in ALLOWED_VIEWS:
            raise UnsafeSqlError(f"tabela não permitida: {table.sql()}")


def _function_name(node: exp.Func) -> str:
    if isinstance(node, exp.Anonymous):
        return str(node.name).lower()
    return str(node.sql_name()).lower()


def _check_functions(tree: exp.Expr) -> None:
    for node in tree.find_all(exp.Func):
        name = _function_name(node)
        if name.startswith(FORBIDDEN_FUNCTION_PREFIXES) or name in FORBIDDEN_FUNCTIONS:
            raise UnsafeSqlError(f"função não permitida: {name}")


def _apply_limit(tree: exp.Query) -> exp.Query:
    limit = tree.args.get("limit")
    if limit is None:
        return tree.limit(DEFAULT_LIMIT, copy=False)
    value = limit.expression
    if not isinstance(value, exp.Literal) or not value.is_int:
        raise UnsafeSqlError("LIMIT precisa ser um número inteiro")
    if int(value.this) > MAX_LIMIT:
        return tree.limit(MAX_LIMIT, copy=False)
    return tree


def validate_sql(sql: str) -> str:
    """Devolve a SQL normalizada e com LIMIT, ou levanta UnsafeSqlError."""
    try:
        statements = [
            statement
            for statement in sqlglot.parse(sql, dialect="postgres")
            if statement is not None
        ]
    except ParseError as error:
        first = error.errors[0]["description"] if error.errors else "erro de sintaxe"
        raise UnsafeSqlError(f"SQL inválida: {first}") from error

    if len(statements) != 1:
        raise UnsafeSqlError("envie exatamente uma consulta")
    tree = statements[0]
    if not isinstance(tree, exp.Query):
        raise UnsafeSqlError("só SELECT é permitido")

    for node in tree.walk():
        if isinstance(node, FORBIDDEN_NODES):
            raise UnsafeSqlError("só SELECT é permitido")
    _check_tables(tree)
    _check_functions(tree)
    return _apply_limit(tree).sql(dialect="postgres")
