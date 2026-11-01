"""Evals sem LLM, para o CI: referências, guardrails e resolução de nomes.

Um runner sem GPU levaria horas com o modelo local, então aqui só entra o que é determinístico.
Falha se uma SQL de referência quebrar ou vier vazia, ou se a busca de provedores errar.
"""

import json
import sys
from pathlib import Path

import psycopg

from telecom_analyst.agent.guardrails.sql import validate_sql
from telecom_analyst.agent.tools.provider_search import FindProviderResult, make_find_provider_tool
from telecom_analyst.agent.tools.sql import execute
from telecom_analyst.config import load_settings

DATASETS = (Path("evals/datasets/sql.jsonl"), Path("evals/datasets/sql_v2.jsonl"))


def load_cases() -> list[dict[str, object]]:
    return [json.loads(line) for path in DATASETS for line in path.read_text().splitlines()]


def main() -> None:
    settings = load_settings()

    def connect() -> psycopg.Connection:
        return psycopg.connect(settings.agent_conninfo)

    cases = load_cases()
    find_provider = make_find_provider_tool(connect)
    failures = []
    references = providers = 0

    for case in cases:
        reference = str(case["sql"])
        if reference:
            references += 1
            rows = execute(connect, validate_sql(reference)).rows
            has_data = any(value is not None for row in rows for value in row)
            if not has_data:
                failures.append(f"{case['id']}: referência sem dados")
        query = case.get("provider_query")
        if query:
            providers += 1
            result = find_provider.run({"nome": query})
            assert isinstance(result, FindProviderResult)  # noqa: S101
            found = result.candidatos[0].agente_nome if result.candidatos else None
            if found != case.get("expected_agent"):
                failures.append(f"{case['id']}: {query} -> {found}")

    print(f"{references} referências e {providers} buscas de provedor conferidas")
    for failure in failures:
        print(f"FALHA {failure}")
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
