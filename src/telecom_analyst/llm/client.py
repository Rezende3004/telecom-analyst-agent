"""Interface única de LLM, isolando o provedor atrás do LiteLLM."""

import json
import time
from typing import Any, Protocol

import litellm
from pydantic import BaseModel, Field

Message = dict[str, Any]


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    # Argumentos que não são JSON válido voltam ao modelo como erro, em vez de derrubar o loop.
    malformed_arguments: str | None = None


class LLMResponse(BaseModel):
    content: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    seconds: float = 0.0


class LLMClient(Protocol):
    def complete(self, messages: list[Message]) -> LLMResponse: ...

    def complete_with_tools(
        self, messages: list[Message], tools: list[dict[str, Any]]
    ) -> LLMResponse: ...


def _parse_tool_call(raw: Any) -> ToolCall:
    arguments = raw.function.arguments
    if isinstance(arguments, dict):
        return ToolCall(id=raw.id, name=raw.function.name, arguments=arguments)
    try:
        parsed = json.loads(arguments or "{}")
    except json.JSONDecodeError:
        parsed = None
    if not isinstance(parsed, dict):
        return ToolCall(id=raw.id, name=raw.function.name, malformed_arguments=str(arguments))
    return ToolCall(id=raw.id, name=raw.function.name, arguments=parsed)


class LiteLLMClient:
    def __init__(self, model: str, api_base: str | None = None, **options: Any) -> None:
        self._model = model
        self._options = {"api_base": api_base, "temperature": 0, "timeout": 300, **options}

    def _call(self, messages: list[Message], **extra: Any) -> LLMResponse:
        started = time.perf_counter()
        response = litellm.completion(
            model=self._model, messages=messages, **self._options, **extra
        )
        message = response.choices[0].message
        return LLMResponse(
            content=message.content or "",
            tool_calls=[_parse_tool_call(call) for call in message.tool_calls or []],
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
            seconds=time.perf_counter() - started,
        )

    def complete(self, messages: list[Message]) -> LLMResponse:
        return self._call(messages)

    def complete_with_tools(
        self, messages: list[Message], tools: list[dict[str, Any]]
    ) -> LLMResponse:
        return self._call(messages, tools=tools)
