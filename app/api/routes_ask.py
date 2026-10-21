from __future__ import annotations

import time

from fastapi import APIRouter

from app.api.deps import AnswererDep, EmbedderDep, SessionDep, SettingsDep
from app.llm import NO_ANSWER, ContextChunk
from app.metrics import ASK_LATENCY, ASK_TOTAL, SOURCES_RETURNED
from app.retrieval import hybrid_search
from app.schemas import AskRequest, AskResponse, SourceOut

router = APIRouter(tags=["ask"])

SNIPPET_CHARS = 400


@router.post("/ask", response_model=AskResponse)
async def ask(
    payload: AskRequest,
    session: SessionDep,
    embedder: EmbedderDep,
    answerer: AnswererDep,
    settings: SettingsDep,
) -> AskResponse:
    started = time.perf_counter()

    effective = (
        settings.model_copy(update={"retrieval_k": payload.top_k}) if payload.top_k else settings
    )
    query_vector = (await embedder.embed([payload.question]))[0]
    chunks = await hybrid_search(session, payload.question, query_vector, effective)

    context = [
        ContextChunk(
            index=position,
            title=chunk.title,
            heading=chunk.heading or "—",
            content=chunk.content,
        )
        for position, chunk in enumerate(chunks, start=1)
    ]
    answer = await answerer.answer(payload.question, context) if context else NO_ANSWER

    latency_ms = (time.perf_counter() - started) * 1000
    ASK_TOTAL.labels(llm=answerer.name, answered=str(bool(context)).lower()).inc()
    ASK_LATENCY.labels(llm=answerer.name).observe(latency_ms / 1000)
    SOURCES_RETURNED.observe(len(chunks))

    return AskResponse(
        answer=answer,
        sources=[
            SourceOut(
                document_id=chunk.document_id,
                title=chunk.title,
                heading=chunk.heading,
                snippet=chunk.content[:SNIPPET_CHARS],
                score=round(chunk.score, 6),
            )
            for chunk in chunks
        ],
        llm=answerer.name,
        embedding_model=embedder.name,
        latency_ms=round(latency_ms, 2),
    )
