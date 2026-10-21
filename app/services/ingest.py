from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chunking import split_document
from app.config import Settings
from app.embeddings import Embedder
from app.models import Chunk, Document


@dataclass(frozen=True, slots=True)
class IngestOutcome:
    document: Document
    chunk_count: int
    created: bool
    written: int


async def ingest_document(
    session: AsyncSession,
    embedder: Embedder,
    settings: Settings,
    *,
    title: str,
    source: str,
    text: str,
) -> IngestOutcome:
    """Chunk, embed and store a document.

    Idempotent by content: the same file ingested twice is a no-op, an edited
    file replaces its chunks. Without this, every re-run of an indexing job
    would multiply the corpus and skew retrieval.
    """
    checksum = hashlib.sha256(text.encode("utf-8")).hexdigest()

    document = await session.scalar(select(Document).where(Document.source == source))
    if document is not None and document.checksum == checksum:
        return IngestOutcome(
            document=document,
            chunk_count=await count_chunks(session, document.id),
            created=False,
            written=0,
        )

    chunks = split_document(text, settings.chunk_size, settings.chunk_overlap)
    if not chunks:
        raise ValueError(f"document {source!r} produced no chunks")

    vectors = await embedder.embed([f"{chunk.heading}\n{chunk.content}" for chunk in chunks])

    created = document is None
    if document is None:
        document = Document(title=title, source=source, checksum=checksum)
        session.add(document)
        await session.flush()
    else:
        # Replace rather than append: old chunks must not survive an edit.
        await session.execute(delete(Chunk).where(Chunk.document_id == document.id))
        document.title = title
        document.checksum = checksum

    session.add_all(
        Chunk(
            document_id=document.id,
            ordinal=chunk.ordinal,
            heading=chunk.heading,
            content=chunk.content,
            token_count=len(chunk.content.split()),
            embedding=vector,
        )
        for chunk, vector in zip(chunks, vectors, strict=True)
    )

    await session.commit()
    await session.refresh(document)
    return IngestOutcome(
        document=document,
        chunk_count=len(chunks),
        created=created,
        written=len(chunks),
    )


async def count_chunks(session: AsyncSession, document_id: uuid.UUID) -> int:
    total = await session.scalar(
        select(func.count()).select_from(Chunk).where(Chunk.document_id == document_id)
    )
    return int(total or 0)


async def list_documents(session: AsyncSession) -> list[tuple[Document, int]]:
    rows = await session.execute(
        select(Document, func.count(Chunk.id))
        .outerjoin(Chunk, Chunk.document_id == Document.id)
        .group_by(Document.id)
        .order_by(Document.created_at.desc())
    )
    return [(document, int(count)) for document, count in rows]


async def delete_document(session: AsyncSession, document_id: uuid.UUID) -> bool:
    exists = await session.scalar(select(Document.id).where(Document.id == document_id))
    if exists is None:
        return False

    # Explicit deletes: the relationship is lazy="raise", so ORM cascades would
    # need a load the mapper is configured to refuse.
    await session.execute(delete(Chunk).where(Chunk.document_id == document_id))
    await session.execute(delete(Document).where(Document.id == document_id))
    await session.commit()
    return True
