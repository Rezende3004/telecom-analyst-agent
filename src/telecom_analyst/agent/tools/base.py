"""Contrato das ferramentas: entrada tipada, descrição lida pelo LLM e saída serializável."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError


class ToolError(Exception):
    """Erro que o modelo pode corrigir. A mensagem volta para ele como resultado."""


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_model: type[BaseModel]
    handler: Callable[[Any], BaseModel]

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_model.model_json_schema(),
            },
        }

    def run(self, arguments: dict[str, Any]) -> BaseModel:
        try:
            parsed = self.input_model.model_validate(arguments)
        except ValidationError as error:
            raise ToolError(f"argumentos inválidos: {error.errors()[0]['msg']}") from error
        return self.handler(parsed)
