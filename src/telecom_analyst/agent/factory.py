"""Monta o agente com a configuração do projeto."""

from pathlib import Path
from typing import Any

import psycopg

from telecom_analyst.agent.entities import HomonymIndex
from telecom_analyst.agent.loop import AgentResult, run_agent
from telecom_analyst.agent.tools.base import Tool
from telecom_analyst.agent.tools.provider_search import make_find_provider_tool
from telecom_analyst.agent.tools.sql import make_run_sql_tool
from telecom_analyst.config import Settings
from telecom_analyst.llm.client import LiteLLMClient, LLMClient

PROMPTS = Path(__file__).parent / "prompts"
SCHEMA_CONTEXT = Path("docs/data-dictionary.md")


def make_llm(settings: Settings) -> LLMClient:
    options: dict[str, Any] = {}
    if settings.llm_model.startswith("ollama"):
        # O Modelfile do Qwen usa presence_penalty 1.5, que pune repetir tokens e estraga
        # nomes de colunas e datas na SQL.
        options = {
            "num_ctx": settings.llm_context_tokens,
            "think": False,
            "presence_penalty": 0,
            "allowed_openai_params": ["presence_penalty"],
        }
    return LiteLLMClient(settings.llm_model, settings.llm_api_base, **options)


def make_tools(settings: Settings) -> list[Tool]:
    def connect() -> psycopg.Connection:
        return psycopg.connect(settings.agent_conninfo)

    return [make_run_sql_tool(connect), make_find_provider_tool(connect)]


def load_homonyms(settings: Settings) -> HomonymIndex:
    query = "SELECT municipio, uf, uf_nome FROM semantic.municipios"
    with psycopg.connect(settings.agent_conninfo) as connection:
        return HomonymIndex(connection.execute(query).fetchall())


def load_snapshot_date(settings: Settings) -> str:
    with psycopg.connect(settings.agent_conninfo) as connection:
        row = connection.execute("SELECT snapshot_date FROM semantic.snapshot").fetchone()
    if row is None:
        raise ValueError("semantic.snapshot está vazia: rode make transform")
    return str(row[0])


def build_system_prompt(settings: Settings) -> str:
    template = (PROMPTS / "system.md").read_text()
    return template.replace("{snapshot_date}", load_snapshot_date(settings)).replace(
        "{schema}", SCHEMA_CONTEXT.read_text()
    )


class Agent:
    def __init__(self, settings: Settings) -> None:
        self._llm = make_llm(settings)
        self._tools = make_tools(settings)
        self._prompt = build_system_prompt(settings)
        self._max_steps = settings.agent_max_steps
        self._homonyms = load_homonyms(settings)

    def ask(self, question: str) -> AgentResult:
        prompt = self._prompt
        note = self._homonyms.note(question)
        if note is not None:
            prompt = f"{prompt}\n\n# Aviso sobre esta pergunta\n\n{note}"
        return run_agent(question, self._llm, self._tools, prompt, self._max_steps)
