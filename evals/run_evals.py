"""Roda as perguntas golden contra um snapshot fixo e grava um relatório.

python -m evals.run_evals --split dev --label v1-base
"""

import argparse
import json
import logging
import statistics
import time
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import litellm
import psycopg
from pydantic import BaseModel

from evals.metrics.result_match import results_match
from telecom_analyst.agent.factory import Agent, load_snapshot_date
from telecom_analyst.agent.loop import AgentResult
from telecom_analyst.agent.tools.sql import execute
from telecom_analyst.config import load_settings

DATASET = Path("evals/datasets/sql.jsonl")
RESULTS = Path("data/evals")
FROZEN_SNAPSHOT = "2026-09-01"
CATEGORIES = ("marca", "grafia", "inexistente", "homonimo", "estrutura")

logger = logging.getLogger(__name__)


class Case(BaseModel):
    id: str
    template: int
    split: str
    difficulty: str
    question: str
    sql: str = ""
    ordered: bool = False
    category: str = ""
    expect_none: bool = False


class Outcome(BaseModel):
    id: str
    split: str
    difficulty: str
    category: str = ""
    question: str
    reference_sql: str
    correct: bool
    verified: bool = False
    exhausted: bool = False
    failure: str | None = None
    agent_sql: str | None = None
    errors: list[str] = []
    answer: str = ""
    steps: int = 0
    tool_calls: int = 0
    tool_errors: int = 0
    seconds: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0


def load_cases(path: Path, split: str) -> list[Case]:
    cases = [Case.model_validate_json(line) for line in path.read_text().splitlines()]
    return [case for case in cases if split == "all" or case.split == split]


def score(case: Case, expected: list[list[Any]], result: AgentResult) -> Outcome:
    final = result.final_result
    failure = None
    if case.expect_none:
        has_data = final is not None and any(
            value is not None for row in final.rows for value in row
        )
        correct = not has_data and not result.exhausted
        failure = None if correct else "trouxe dados de provedor inexistente"
    else:
        correct = final is not None and results_match(expected, final.rows, ordered=case.ordered)
        if result.exhausted:
            failure = "limite de passos"
        elif final is None:
            failure = "nenhuma consulta válida"
        elif not correct:
            failure = "resultado diferente"
    llm_steps = [step for step in result.steps if step.kind == "llm"]
    tool_steps = [step for step in result.steps if step.kind == "tool"]
    return Outcome(
        id=case.id,
        split=case.split,
        difficulty=case.difficulty,
        category=case.category,
        question=case.question,
        reference_sql=case.sql,
        correct=correct,
        verified=result.verified,
        exhausted=result.exhausted,
        failure=failure,
        agent_sql=result.queries[-1] if result.queries else None,
        errors=[step.error for step in tool_steps if step.error],
        answer=result.answer,
        steps=len(llm_steps),
        tool_calls=len(tool_steps),
        tool_errors=result.tool_errors,
        seconds=result.seconds,
        input_tokens=sum(step.input_tokens for step in llm_steps),
        output_tokens=sum(step.output_tokens for step in llm_steps),
    )


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(int(len(ordered) * fraction), len(ordered) - 1)]


def accuracy_line(name: str, outcomes: list[Outcome]) -> str:
    hits = sum(outcome.correct for outcome in outcomes)
    return f"| {name} | {hits} de {len(outcomes)} | {100 * hits / len(outcomes):.0f}% |"


def summarize(outcomes: Iterable[Outcome], label: str, model: str) -> str:
    items = list(outcomes)
    calls = sum(item.tool_calls for item in items)
    seconds = [item.seconds for item in items]
    lines = [
        f"# Evals: {label}",
        "",
        f"Modelo `{model}`, snapshot {FROZEN_SNAPSHOT}.",
        "",
        "| Conjunto | Acertos | Execution accuracy |",
        "| --- | --- | --- |",
        accuracy_line("**Todos**", items),
    ]
    groups: defaultdict[str, list[Outcome]] = defaultdict(list)
    for item in items:
        groups[f"split {item.split}"].append(item)
        groups[item.difficulty].append(item)
        if item.category:
            groups[item.category].append(item)
    names = ("split dev", "split test", "facil", "media", "dificil", *CATEGORIES)
    for name in names:
        if name in groups:
            lines.append(accuracy_line(name, groups[name]))
    lines += [
        "",
        "| Métrica | Valor |",
        "| --- | --- |",
        f"| SQL recusada ou com erro | {sum(i.tool_errors for i in items)} de {calls} chamadas |",
        f"| Perguntas sem consulta válida | {sum(i.agent_sql is None for i in items)} |",
        f"| Limite de passos atingido | {sum(i.exhausted for i in items)} |",
        f"| Verificação de números aprovada | {sum(i.verified for i in items)} de {len(items)} |",
        f"| Passos de LLM por pergunta (média) | {statistics.mean(i.steps for i in items):.1f} |",
        f"| Latência p50 | {percentile(seconds, 0.5):.1f} s |",
        f"| Latência p95 | {percentile(seconds, 0.95):.1f} s |",
        f"| Tokens por pergunta (média) | "
        f"{statistics.mean(i.input_tokens + i.output_tokens for i in items):.0f} |",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=["dev", "test", "all"], default="dev")
    parser.add_argument("--label", required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dataset", type=Path, default=DATASET)
    arguments = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("LiteLLM").setLevel(logging.ERROR)
    litellm.suppress_debug_info = True

    settings = load_settings()
    snapshot = load_snapshot_date(settings)
    if snapshot != FROZEN_SNAPSHOT:
        raise SystemExit(f"o banco está no snapshot {snapshot}, esperava {FROZEN_SNAPSHOT}")

    cases = load_cases(arguments.dataset, arguments.split)[: arguments.limit]
    agent = Agent(settings)
    RESULTS.mkdir(parents=True, exist_ok=True)
    output = RESULTS / f"{arguments.label}.jsonl"

    def connect() -> psycopg.Connection:
        return psycopg.connect(settings.agent_conninfo)

    outcomes = []
    started = time.perf_counter()
    with output.open("w") as stream:
        for number, case in enumerate(cases, start=1):
            expected = execute(connect, case.sql).rows if case.sql else []
            try:
                outcome = score(case, expected, agent.ask(case.question))
            except Exception as error:
                logger.exception("falha em %s", case.id)
                outcome = Outcome(
                    id=case.id,
                    split=case.split,
                    difficulty=case.difficulty,
                    question=case.question,
                    reference_sql=case.sql,
                    correct=False,
                    failure=f"exceção: {type(error).__name__}",
                )
            outcomes.append(outcome)
            stream.write(outcome.model_dump_json() + "\n")
            stream.flush()
            logger.info(
                "%d/%d %s %s", number, len(cases), "ok " if outcome.correct else "ERRO", case.id
            )

    report = summarize(outcomes, arguments.label, settings.llm_model)
    (RESULTS / f"{arguments.label}.md").write_text(report)
    print(report)
    print(json.dumps({"minutos": round((time.perf_counter() - started) / 60, 1)}))


if __name__ == "__main__":
    main()
