from __future__ import annotations

import os
import tempfile
import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.db import get_session
from app.main import create_app
from app.models import Base

SAMPLE_DOCUMENT = """# Deploy process

## Rollback

The rollback procedure takes under ten minutes and is rehearsed quarterly.

## Feature flags

Risky changes ship behind a feature flag that is removed after two weeks.
"""


@pytest.fixture(scope="session")
def database_url():
    """Prefer an external database (CI service container), else start pgserver."""
    explicit = os.getenv("TEST_DATABASE_URL")
    if explicit:
        yield explicit
        return

    import pgserver

    server = pgserver.get_server(tempfile.mkdtemp(prefix="rag-pg-"), cleanup_mode="stop")
    try:
        server.psql("CREATE DATABASE rag_test;")
        base, _ = server.get_uri().rsplit("/", 1)
        yield "postgresql+asyncpg://" + (base + "/rag_test").split("://", 1)[1]
    finally:
        server.cleanup()


@pytest_asyncio.fixture
async def engine(database_url: str):
    engine = create_async_engine(database_url, poolclass=NullPool)
    async with engine.begin() as connection:
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session(engine) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(engine) -> AsyncIterator[AsyncClient]:
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    app = create_app()

    async def _override() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client


async def ingest(client: AsyncClient, source: str = "runbooks/deploy.md", **overrides) -> dict:
    payload = {
        "title": "Deploy process",
        "source": source,
        "text": SAMPLE_DOCUMENT,
        **overrides,
    }
    response = await client.post("/api/v1/documents", json=payload)
    assert response.status_code in (200, 201), response.text
    return response.json()


@pytest.fixture
def document_id() -> uuid.UUID:
    return uuid.uuid4()
