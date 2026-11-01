"""Loop do agente: planeja, chama ferramenta, verifica e responde."""

import json
import logging
import time
from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from telecom_analyst.agent.tools.base import Tool, ToolError
from telecom_analyst.agent.tools.provider_search import FindProviderResult
from telecom_analyst.agent.tools.sql import SqlResult
from telecom_analyst.agent.verification import find_unsupported, flatten_numbers
from telecom_analyst.llm.client import LLMClient, LLMResponse, Message, ToolCall

logger = logging.getLogger(__name__)

EXHAUSTED_ANSWER = "Não consegui chegar a uma resposta confiável dentro do limite de passos."
UNVERIFIED_NOTE = "Aviso: a verificação não encontrou a origem destes números: {numbers}."
REPEATED_FAILURE = (
    "Você repetiu uma chamada que já falhou com este erro: {error} "
    "Escreva uma consulta diferente, mais simples, sobre uma única view."
)
MAX_REPEATED_FAILURES = 2
VERIFICATION_FEEDBACK = (
    "Os números {numbers} não aparecem nos resultados das ferramentas. Reescreva a resposta "
    "usando só valores que vieram das consultas, ou consulte de novo."
)


class Step(BaseModel):
    kind: str  # "llm" ou "tool"
    seconds: float
    tool: str | None = None
    arguments: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0


class AgentResult(BaseModel):
    question: str
    answer: str
    verified: bool
    exhausted: bool = False
    steps: list[Step] = Field(default_factory=list)
    queries: list[str] = Field(default_factory=list)
    final_result: SqlResult | None = None

    @property
    def seconds(self) -> float:
        return sum(step.seconds for step in self.steps)

    @property
    def tool_errors(self) -> int:
        return sum(step.error is not None for step in self.steps)


def _assistant_message(response: LLMResponse) -> Message:
    calls = [
        {
            "id": call.id,
            "type": "function",
            "function": {
                "name": call.name,
                "arguments": call.malformed_arguments or json.dumps(call.arguments),
            },
        }
        for call in response.tool_calls
    ]
    return {"role": "assistant", "content": response.content, "tool_calls": calls}


def _run_tool(tools: dict[str, Tool], call: ToolCall) -> tuple[BaseModel | None, str | None]:
    if call.malformed_arguments is not None:
        return None, f"argumentos não são JSON válido: {call.malformed_arguments[:200]}"
    tool = tools.get(call.name)
    if tool is None:
        return None, f"ferramenta desconhecida: {call.name}"
    try:
        return tool.run(call.arguments), None
    except ToolError as error:
        return None, str(error)


def run_agent(
    question: str,
    llm: LLMClient,
    tools: Sequence[Tool],
    system_prompt: str,
    max_steps: int = 6,
) -> AgentResult:
    by_name = {tool.name: tool for tool in tools}
    schemas = [tool.schema() for tool in tools]
    messages: list[Message] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]
    result = AgentResult(question=question, answer=EXHAUSTED_ANSWER, verified=False)
    numbers: list[Decimal] = []
    feedback_given = False
    failures: dict[str, str] = {}
    repeated_failures = 0

    for _ in range(max_steps):
        response = llm.complete_with_tools(messages, schemas)
        result.steps.append(
            Step(
                kind="llm",
                seconds=response.seconds,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
            )
        )

        if not response.tool_calls:
            unsupported = find_unsupported(response.content, numbers, question)
            if unsupported and not feedback_given:
                feedback_given = True
                text = ", ".join(unsupported)
                messages.append({"role": "assistant", "content": response.content})
                messages.append(
                    {"role": "user", "content": VERIFICATION_FEEDBACK.format(numbers=text)}
                )
                continue
            result.verified = not unsupported
            result.answer = response.content
            if unsupported:
                note = UNVERIFIED_NOTE.format(numbers=", ".join(unsupported))
                result.answer = f"{response.content}\n\n{note}"
            return result

        messages.append(_assistant_message(response))
        for call in response.tool_calls:
            signature = f"{call.name}:{json.dumps(call.arguments, sort_keys=True)}"
            if signature in failures:
                repeated_failures += 1
                warning = REPEATED_FAILURE.format(error=failures[signature])
                result.steps.append(Step(kind="tool", seconds=0, tool=call.name, error=warning))
                messages.append({"role": "tool", "tool_call_id": call.id, "content": warning})
                continue

            started = time.perf_counter()
            output, error = _run_tool(by_name, call)
            if error is not None:
                failures[signature] = error
            step = Step(
                kind="tool",
                seconds=time.perf_counter() - started,
                tool=call.name,
                arguments=call.arguments,
                error=error,
            )
            if isinstance(output, SqlResult):
                step.result = output.model_dump()
                result.queries.append(output.query)
                result.final_result = output
                numbers.extend(flatten_numbers(output.rows))
            elif isinstance(output, FindProviderResult):
                step.result = output.model_dump()
                numbers.extend(Decimal(c.acessos_atuais) for c in output.candidatos)
            result.steps.append(step)
            content = output.model_dump_json() if output is not None else f"ERRO: {error}"
            messages.append({"role": "tool", "tool_call_id": call.id, "content": content})

        if repeated_failures >= MAX_REPEATED_FAILURES:
            break

    result.exhausted = True
    logger.warning("limite de passos atingido: %s", question)
    return result
