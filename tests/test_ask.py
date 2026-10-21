from __future__ import annotations

from conftest import ingest
from httpx import AsyncClient

from app.llm import NO_ANSWER


async def test_answer_cites_retrieved_sources(client: AsyncClient) -> None:
    await ingest(client)

    response = await client.post(
        "/api/v1/ask",
        json={"question": "How long does the rollback procedure take?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "[" in body["answer"]
    assert body["sources"]
    assert body["llm"] == "stub-extractive"
    assert body["embedding_model"].startswith("hash-")
    assert body["latency_ms"] >= 0


async def test_answer_is_deterministic(client: AsyncClient) -> None:
    await ingest(client)
    payload = {"question": "What happens to risky changes?"}

    first = (await client.post("/api/v1/ask", json=payload)).json()
    second = (await client.post("/api/v1/ask", json=payload)).json()

    assert first["answer"] == second["answer"]
    assert [source["snippet"] for source in first["sources"]] == [
        source["snippet"] for source in second["sources"]
    ]


async def test_top_k_limits_the_number_of_sources(client: AsyncClient) -> None:
    await ingest(client)

    body = (
        await client.post(
            "/api/v1/ask",
            json={"question": "How long does the rollback procedure take?", "top_k": 1},
        )
    ).json()

    assert len(body["sources"]) == 1


async def test_empty_index_reports_no_answer(client: AsyncClient) -> None:
    body = (
        await client.post("/api/v1/ask", json={"question": "What is the rollback timeout?"})
    ).json()

    assert body["answer"] == NO_ANSWER
    assert body["sources"] == []
