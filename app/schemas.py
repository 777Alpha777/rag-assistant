from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentIngest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    source: str = Field(min_length=1, max_length=512, examples=["runbooks/deploy.md"])
    text: str = Field(min_length=1)


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    source: str
    chunk_count: int
    created_at: datetime


class IngestResult(BaseModel):
    document: DocumentOut
    created: bool


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    top_k: int | None = Field(default=None, ge=1, le=20)


class SourceOut(BaseModel):
    document_id: uuid.UUID
    title: str
    heading: str
    snippet: str
    score: float


class AskResponse(BaseModel):
    answer: str
    sources: list[SourceOut]
    llm: str
    embedding_model: str
    latency_ms: float
