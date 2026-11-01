"""Ferramenta run_sql: consulta as views semânticas com o usuário somente leitura."""

from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import psycopg
from psycopg import sql as pg_sql
from pydantic import BaseModel, Field

from telecom_analyst.agent.guardrails.sql import UnsafeSqlError, validate_sql
from telecom_analyst.agent.tools.base import Tool, ToolError

MAX_ROWS_FOR_MODEL = 50
Connect = Callable[[], psycopg.Connection]


class RunSqlInput(BaseModel):
    sql: str = Field(description="Uma consulta SELECT sobre as views do schema semantic.")


class SqlResult(BaseModel):
    query: str
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    truncated: bool = False


def _serialize(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    return value


def execute(connect: Connect, query: str) -> SqlResult:
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute(pg_sql.SQL(query))
        columns = [column.name for column in cursor.description or []]
        rows = [[_serialize(value) for value in row] for row in cursor.fetchall()]
    return SqlResult(query=query, columns=columns, rows=rows, row_count=len(rows))


def run_sql(connect: Connect, sql: str) -> SqlResult:
    try:
        query = validate_sql(sql)
    except UnsafeSqlError as error:
        raise ToolError(str(error)) from error
    try:
        result = execute(connect, query)
    except psycopg.Error as error:
        message = str(error).strip().splitlines()[0]
        raise ToolError(f"erro ao executar a SQL: {message}") from error

    if result.row_count > MAX_ROWS_FOR_MODEL:
        result.rows = result.rows[:MAX_ROWS_FOR_MODEL]
        result.truncated = True
    return result


def make_run_sql_tool(connect: Connect) -> Tool:
    def handler(arguments: RunSqlInput) -> SqlResult:
        return run_sql(connect, arguments.sql)

    return Tool(
        name="run_sql",
        description=(
            "Executa uma consulta SELECT em PostgreSQL sobre as views do schema semantic e "
            "devolve as linhas. Se a consulta falhar, o erro volta para você corrigir."
        ),
        input_model=RunSqlInput,
        handler=handler,
    )
