"""API do agente: POST /ask recebe a pergunta e devolve a resposta com as fontes."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field, computed_field

from telecom_analyst.agent.factory import Agent
from telecom_analyst.agent.loop import AgentResult, Step
from telecom_analyst.config import load_settings

MAX_QUESTION_LENGTH = 500


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=MAX_QUESTION_LENGTH)


class AskResponse(BaseModel):
    answer: str
    verified: bool
    queries: list[str]
    steps: list[Step]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def seconds(self) -> float:
        return sum(step.seconds for step in self.steps)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.agent = Agent(load_settings())
    yield


# O modelo local atende uma pergunta por vez.
model_lock = asyncio.Lock()
app = FastAPI(title="Analista de Mercado Telecom", lifespan=lifespan)


def get_agent(request: Request) -> Agent:
    agent: Agent = request.app.state.agent
    return agent


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/ask")
async def ask(body: AskRequest, agent: Annotated[Agent, Depends(get_agent)]) -> AskResponse:
    async with model_lock:
        try:
            result: AgentResult = await asyncio.to_thread(agent.ask, body.question)
        except Exception as error:
            raise HTTPException(status_code=503, detail="agente indisponível") from error
    return AskResponse(
        answer=result.answer,
        verified=result.verified,
        queries=result.queries,
        steps=result.steps,
    )
