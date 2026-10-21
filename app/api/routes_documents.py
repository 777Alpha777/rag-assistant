from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Response, status

from app.api.deps import EmbedderDep, SessionDep, SettingsDep
from app.metrics import CHUNKS_INDEXED, DOCUMENTS_INGESTED
from app.schemas import DocumentIngest, DocumentOut, IngestResult
from app.services import ingest as ingest_service

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "",
    response_model=IngestResult,
    status_code=status.HTTP_201_CREATED,
    responses={200: {"description": "Same content already ingested — nothing changed"}},
)
async def ingest_document(
    payload: DocumentIngest,
    response: Response,
    session: SessionDep,
    embedder: EmbedderDep,
    settings: SettingsDep,
) -> IngestResult:
    outcome = await ingest_service.ingest_document(
        session,
        embedder,
        settings,
        title=payload.title,
        source=payload.source,
        text=payload.text,
    )
    if not outcome.created:
        response.status_code = status.HTTP_200_OK

    DOCUMENTS_INGESTED.labels(created=str(outcome.created).lower()).inc()
    CHUNKS_INDEXED.inc(outcome.written)

    document = outcome.document
    return IngestResult(
        document=DocumentOut(
            id=document.id,
            title=document.title,
            source=document.source,
            chunk_count=outcome.chunk_count,
            created_at=document.created_at,
        ),
        created=outcome.created,
    )


@router.get("", response_model=list[DocumentOut])
async def list_documents(session: SessionDep) -> list[DocumentOut]:
    rows = await ingest_service.list_documents(session)
    return [
        DocumentOut(
            id=document.id,
            title=document.title,
            source=document.source,
            chunk_count=count,
            created_at=document.created_at,
        )
        for document, count in rows
    ]


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: uuid.UUID, session: SessionDep) -> Response:
    deleted = await ingest_service.delete_document(session, document_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
