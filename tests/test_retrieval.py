from __future__ import annotations

import uuid

from conftest import ingest
from httpx import AsyncClient

from app.retrieval import RetrievedChunk, build_tsquery, reciprocal_rank_fusion


def make_chunk(
    chunk_id: int,
    heading: str,
    *,
    vector_rank: int | None = None,
    text_rank: int | None = None,
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        document_id=uuid.uuid4(),
        title="doc",
        heading=heading,
        content="content",
        score=0.0,
        vector_rank=vector_rank,
        text_rank=text_rank,
    )


def test_rrf_prefers_a_document_found_by_both_retrievers() -> None:
    dense = [make_chunk(1, "a", vector_rank=1), make_chunk(2, "b", vector_rank=2)]
    lexical = [make_chunk(2, "b", text_rank=1), make_chunk(3, "c", text_rank=2)]

    fused = reciprocal_rank_fusion(dense, lexical)

    assert fused[0].chunk_id == 2
    assert {chunk.chunk_id for chunk in fused} == {1, 2, 3}


def test_rrf_keeps_provenance_of_each_candidate() -> None:
    fused = reciprocal_rank_fusion(
        [make_chunk(1, "a", vector_rank=1)],
        [make_chunk(1, "a", text_rank=1)],
    )

    assert fused[0].vector_rank == 1
    assert fused[0].text_rank == 1


def test_tsquery_becomes_an_or_expression() -> None:
    assert build_tsquery("How long does a rollback take?") == (
        "how | long | does | a | rollback | take"
    )
    assert build_tsquery("   ") == ""


async def test_hybrid_search_finds_the_right_section(client: AsyncClient) -> None:
    await ingest(client)

    response = await client.post(
        "/api/v1/ask",
        json={"question": "How long does the rollback procedure take?"},
    )

    assert response.status_code == 200
    sources = response.json()["sources"]
    assert sources
    assert "Rollback" in sources[0]["heading"]
