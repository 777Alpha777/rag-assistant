"""Hybrid retrieval: dense vectors + full-text, fused with Reciprocal Rank Fusion.

Why both: embeddings answer "what is this about", full-text answers "does this
contain the exact term". In an internal knowledge base the second one matters —
error codes, config keys and service names are not semantically fuzzy.
Why RRF: it needs no score calibration between two incomparable scales, only
the ranks, and it is one line of arithmetic to explain.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, replace

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings

ALLOWED_TEXT_CONFIGS = {"simple", "russian", "english"}

VECTOR_SQL = text(
    """
    SELECT c.id AS chunk_id, c.document_id, d.title, c.heading, c.content,
           1 - (c.embedding <=> CAST(:embedding AS vector)) AS score
    FROM chunks c
    JOIN documents d ON d.id = c.document_id
    ORDER BY c.embedding <=> CAST(:embedding AS vector)
    LIMIT :limit
    """
)

TEXT_SQL = text(
    """
    SELECT c.id AS chunk_id, c.document_id, d.title, c.heading, c.content,
           ts_rank_cd(c.tsv, to_tsquery(CAST(:config AS regconfig), :query)) AS score
    FROM chunks c
    JOIN documents d ON d.id = c.document_id
    WHERE c.tsv @@ to_tsquery(CAST(:config AS regconfig), :query)
    ORDER BY score DESC, c.id
    LIMIT :limit
    """
)

TOKEN_RE = re.compile(r"[0-9a-zA-Z_\u0400-\u04ff]+")


def build_tsquery(query: str) -> str:
    """Turn a natural-language question into an OR query.

    ``plainto_tsquery`` joins terms with AND, which for a full question ("how long
    does a rollback take") matches almost nothing. OR keeps recall high; the
    ranking and the vector side sort out relevance.
    """
    return " | ".join(TOKEN_RE.findall(query.lower()))


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    chunk_id: int
    document_id: uuid.UUID
    title: str
    heading: str
    content: str
    score: float
    vector_rank: int | None = None
    text_rank: int | None = None


def _to_vector_literal(embedding: list[float]) -> str:
    return "[" + ",".join(f"{value:.6f}" for value in embedding) + "]"


async def vector_search(
    session: AsyncSession, embedding: list[float], limit: int
) -> list[RetrievedChunk]:
    rows = await session.execute(
        VECTOR_SQL,
        {"embedding": _to_vector_literal(embedding), "limit": limit},
    )
    return [
        RetrievedChunk(
            chunk_id=row.chunk_id,
            document_id=row.document_id,
            title=row.title,
            heading=row.heading,
            content=row.content,
            score=float(row.score),
            vector_rank=index + 1,
        )
        for index, row in enumerate(rows)
    ]


async def text_search(
    session: AsyncSession, query: str, limit: int, config: str = "simple"
) -> list[RetrievedChunk]:
    if config not in ALLOWED_TEXT_CONFIGS:
        raise ValueError(f"unsupported text search config: {config}")

    tsquery = build_tsquery(query)
    if not tsquery:
        return []

    rows = await session.execute(TEXT_SQL, {"query": tsquery, "config": config, "limit": limit})
    return [
        RetrievedChunk(
            chunk_id=row.chunk_id,
            document_id=row.document_id,
            title=row.title,
            heading=row.heading,
            content=row.content,
            score=float(row.score),
            text_rank=index + 1,
        )
        for index, row in enumerate(rows)
    ]


def reciprocal_rank_fusion(
    *rankings: list[RetrievedChunk],
    k: int = 60,
    weights: Sequence[float] | None = None,
) -> list[RetrievedChunk]:
    """Fuse ranked lists: score = sum(weight / (k + rank)) over every list.

    Weights exist because the two retrievers are not equally trustworthy on a
    small corpus: the lexical side uses OR-matching, so a chunk that merely
    repeats common words can top its ranking. Rank alone cannot express that,
    which is why the dense list is weighted higher by default.
    """
    if weights is not None and len(weights) != len(rankings):
        raise ValueError("weights must match the number of rankings")

    fused: dict[int, RetrievedChunk] = {}
    scores: dict[int, float] = {}

    for position_in_fusion, ranking in enumerate(rankings):
        weight = 1.0 if weights is None else weights[position_in_fusion]
        for position, chunk in enumerate(ranking, start=1):
            existing = fused.get(chunk.chunk_id)
            if existing is None:
                fused[chunk.chunk_id] = chunk
            else:
                fused[chunk.chunk_id] = replace(
                    existing,
                    vector_rank=existing.vector_rank or chunk.vector_rank,
                    text_rank=existing.text_rank or chunk.text_rank,
                )
            scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + weight / (k + position)

    ordered = sorted(fused.values(), key=lambda chunk: scores[chunk.chunk_id], reverse=True)
    return [replace(chunk, score=scores[chunk.chunk_id]) for chunk in ordered]


async def hybrid_search(
    session: AsyncSession,
    query: str,
    embedding: list[float],
    settings: Settings,
) -> list[RetrievedChunk]:
    dense = await vector_search(session, embedding, settings.candidate_k)
    lexical = await text_search(session, query, settings.candidate_k, settings.text_search_config)
    fused = reciprocal_rank_fusion(
        dense, lexical, k=settings.rrf_k, weights=(1.0, settings.lexical_weight)
    )
    return fused[: settings.retrieval_k]
