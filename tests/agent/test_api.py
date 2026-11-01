import pytest
from fastapi.testclient import TestClient

from telecom_analyst.agent.loop import AgentResult
from telecom_analyst.api.main import MAX_QUESTION_LENGTH, app, get_agent


class FakeAgent:
    def ask(self, question: str) -> AgentResult:
        if question == "falha":
            raise RuntimeError("modelo fora do ar")
        return AgentResult(
            question=question, answer="São 10 acessos.", verified=True, queries=["Q"]
        )


@pytest.fixture
def client() -> TestClient:
    app.dependency_overrides[get_agent] = FakeAgent
    return TestClient(app)


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_ask_returns_answer_and_sources(client: TestClient) -> None:
    response = client.post("/ask", json={"question": "Quantos acessos?"})

    assert response.status_code == 200
    assert response.json()["answer"] == "São 10 acessos."
    assert response.json()["queries"] == ["Q"]


@pytest.mark.parametrize("question", ["", "x" * (MAX_QUESTION_LENGTH + 1)])
def test_rejects_invalid_question(client: TestClient, question: str) -> None:
    assert client.post("/ask", json={"question": question}).status_code == 422


def test_agent_failure_hides_details(client: TestClient) -> None:
    response = client.post("/ask", json={"question": "falha"})

    assert response.status_code == 503
    assert "modelo" not in response.text
