"""Confere que cada serviço da stack está no ar e configurado como o projeto espera."""

import os
import time

import httpx
import psycopg
import pytest

from telecom_analyst.config import Settings

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


def test_postgres_is_version_16(settings: Settings) -> None:
    with psycopg.connect(settings.postgres_conninfo) as conn:
        row = conn.execute("SHOW server_version_num").fetchone()

    assert row is not None
    assert row[0].startswith("16")


def test_pgvector_orders_by_distance(settings: Settings) -> None:
    query = """
        SELECT id
        FROM (VALUES (1, '[0, 1]'::vector), (2, '[1, 0]'::vector)) AS t(id, embedding)
        ORDER BY embedding <=> '[1, 0.1]'::vector
        LIMIT 1
    """
    with psycopg.connect(settings.postgres_conninfo) as conn:
        row = conn.execute(query).fetchone()

    assert row == (2,)


def test_langfuse_database_is_closed_to_public(settings: Settings) -> None:
    query = "SELECT has_database_privilege('public', 'langfuse', 'CONNECT')"
    with psycopg.connect(settings.postgres_conninfo) as conn:
        row = conn.execute(query).fetchone()

    assert row == (False,)


def test_mlflow_is_healthy(settings: Settings) -> None:
    response = httpx.get(f"{settings.mlflow_url}/health")

    assert response.status_code == httpx.codes.OK


def test_langfuse_accepts_project_keys(settings: Settings) -> None:
    response = httpx.get(
        f"{settings.langfuse_url}/api/public/projects",
        auth=(settings.langfuse_public_key, settings.langfuse_secret_key.get_secret_value()),
    )

    assert response.status_code == httpx.codes.OK
    assert [project["name"] for project in response.json()["data"]] == ["telecom-analyst"]


def test_langfuse_stores_otlp_span(settings: Settings) -> None:
    auth = (settings.langfuse_public_key, settings.langfuse_secret_key.get_secret_value())
    trace_id = os.urandom(16).hex()
    now = time.time_ns()
    span = {
        "traceId": trace_id,
        "spanId": os.urandom(8).hex(),
        "name": "stack-check",
        "kind": 1,
        "startTimeUnixNano": str(now - 1_000_000),
        "endTimeUnixNano": str(now),
    }
    payload = {"resourceSpans": [{"scopeSpans": [{"scope": {"name": "tests"}, "spans": [span]}]}]}

    response = httpx.post(
        f"{settings.langfuse_url}/api/public/otel/v1/traces", auth=auth, json=payload
    )
    assert response.status_code == httpx.codes.OK

    observations: list[dict[str, str]] = []
    deadline = time.monotonic() + 60
    while not observations and time.monotonic() < deadline:
        time.sleep(1)
        observations = httpx.get(
            f"{settings.langfuse_url}/api/public/v2/observations",
            auth=auth,
            params={"traceId": trace_id, "fields": "core,basic"},
        ).json()["data"]

    assert [observation["name"] for observation in observations] == ["stack-check"]
