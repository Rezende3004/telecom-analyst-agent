from typing import Any

from pydantic import BaseModel

from telecom_analyst.agent.loop import EXHAUSTED_ANSWER, run_agent
from telecom_analyst.agent.tools.base import Tool, ToolError
from telecom_analyst.agent.tools.sql import RunSqlInput, SqlResult
from telecom_analyst.llm.client import LLMResponse, Message, ToolCall


class ScriptedLLM:
    """LLM falso que devolve respostas prontas e guarda o que recebeu."""

    def __init__(self, *responses: LLMResponse) -> None:
        self.responses = list(responses)
        self.calls: list[list[Message]] = []

    def complete(self, messages: list[Message]) -> LLMResponse:
        raise NotImplementedError

    def complete_with_tools(
        self, messages: list[Message], tools: list[dict[str, Any]]
    ) -> LLMResponse:
        self.calls.append(list(messages))
        return self.responses.pop(0)


def sql_call(sql: str = "SELECT 1") -> LLMResponse:
    return LLMResponse(tool_calls=[ToolCall(id="1", name="run_sql", arguments={"sql": sql})])


def text(content: str) -> LLMResponse:
    return LLMResponse(content=content)


def fake_tool(*outputs: BaseModel | ToolError) -> Tool:
    queue = list(outputs)

    def handler(_: RunSqlInput) -> BaseModel:
        output = queue.pop(0)
        if isinstance(output, ToolError):
            raise output
        return output

    return Tool("run_sql", "Executa SQL.", RunSqlInput, handler)


def rows(*values: int) -> SqlResult:
    return SqlResult(
        query="SELECT x", columns=["x"], rows=[[value] for value in values], row_count=len(values)
    )


def run(llm: ScriptedLLM, tool: Tool, question: str = "Quantos acessos?", steps: int = 6) -> Any:
    return run_agent(question, llm, [tool], "sistema", max_steps=steps)


def test_returns_answer_with_query_as_citation() -> None:
    llm = ScriptedLLM(sql_call(), text("São 72.978 acessos."))

    result = run(llm, fake_tool(rows(72978)))

    assert result.answer == "São 72.978 acessos."
    assert result.verified
    assert result.queries == ["SELECT x"]


def test_sql_error_goes_back_to_the_model() -> None:
    llm = ScriptedLLM(sql_call("SELECT a"), sql_call("SELECT b"), text("São 72.978 acessos."))

    result = run(llm, fake_tool(ToolError("coluna inexistente"), rows(72978)))

    tool_message = llm.calls[1][-1]
    assert tool_message["role"] == "tool"
    assert "coluna inexistente" in tool_message["content"]
    assert result.tool_errors == 1
    assert result.verified


def test_invented_number_triggers_one_correction() -> None:
    llm = ScriptedLLM(sql_call(), text("São 99.999 acessos."), text("São 72.978 acessos."))

    result = run(llm, fake_tool(rows(72978)))

    assert "99.999" in llm.calls[2][-1]["content"]
    assert result.answer == "São 72.978 acessos."
    assert result.verified


def test_repeated_invented_number_is_flagged_in_the_answer() -> None:
    llm = ScriptedLLM(sql_call(), text("São 99.999 acessos."), text("Insisto em 99.999 acessos."))

    result = run(llm, fake_tool(rows(72978)))

    assert not result.verified
    assert "Aviso" in result.answer
    assert "99.999" in result.answer


def test_stops_at_step_limit() -> None:
    llm = ScriptedLLM(sql_call(), sql_call(), sql_call())

    result = run(llm, fake_tool(rows(1), rows(2), rows(3)), steps=2)

    assert result.exhausted
    assert result.answer == EXHAUSTED_ANSWER
    assert not result.verified


def test_unknown_tool_is_reported_to_the_model() -> None:
    call = LLMResponse(tool_calls=[ToolCall(id="1", name="apagar_tudo", arguments={})])
    llm = ScriptedLLM(call, text("Não consegui."))

    run(llm, fake_tool())

    assert "ferramenta desconhecida" in llm.calls[1][-1]["content"]


def test_malformed_arguments_are_reported_to_the_model() -> None:
    call = LLMResponse(tool_calls=[ToolCall(id="1", name="run_sql", malformed_arguments="{sql")])
    llm = ScriptedLLM(call, text("Não consegui."))

    run(llm, fake_tool())

    assert "não são JSON" in llm.calls[1][-1]["content"]


def test_answer_without_numbers_needs_no_tool() -> None:
    llm = ScriptedLLM(text("Essa pergunta está fora do que estes dados cobrem."))

    result = run(llm, fake_tool())

    assert result.verified
    assert result.queries == []


def test_repeated_failed_call_is_not_executed_again() -> None:
    llm = ScriptedLLM(sql_call(), sql_call(), text("Não consegui."))
    tool = fake_tool(ToolError("coluna inexistente"))

    result = run(llm, tool)

    assert "repetiu" in llm.calls[2][-1]["content"]
    assert result.tool_errors == 2


def test_stops_early_when_model_insists_on_failed_call() -> None:
    llm = ScriptedLLM(sql_call(), sql_call(), sql_call(), sql_call(), sql_call())

    result = run(llm, fake_tool(ToolError("coluna inexistente")))

    assert result.exhausted
    assert len(llm.calls) == 3
