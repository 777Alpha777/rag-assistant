from __future__ import annotations

from conftest import ingest
from httpx import AsyncClient


async def test_ingest_creates_chunks(client: AsyncClient) -> None:
    body = await ingest(client)

    assert body["created"] is True
    assert body["document"]["chunk_count"] >= 2
    assert body["document"]["source"] == "runbooks/deploy.md"


async def test_reingesting_same_content_is_a_noop(client: AsyncClient) -> None:
    first = await ingest(client)
    second = await ingest(client)

    assert second["created"] is False
    assert second["document"]["id"] == first["document"]["id"]
    assert second["document"]["chunk_count"] == first["document"]["chunk_count"]


async def test_changed_content_replaces_chunks(client: AsyncClient) -> None:
    first = await ingest(client)
    second = await ingest(client, text="# Deploy process\n\n## Rollback\n\nShort new body.")

    assert second["created"] is False
    assert second["document"]["id"] == first["document"]["id"]
    assert second["document"]["chunk_count"] == 1


async def test_list_and_delete(client: AsyncClient) -> None:
    body = await ingest(client)

    listing = (await client.get("/api/v1/documents")).json()
    assert len(listing) == 1
    assert listing[0]["chunk_count"] == body["document"]["chunk_count"]

    deleted = await client.delete(f"/api/v1/documents/{body['document']['id']}")
    assert deleted.status_code == 204
    assert (await client.get("/api/v1/documents")).json() == []


async def test_deleting_unknown_document_returns_404(client: AsyncClient) -> None:
    response = await client.delete("/api/v1/documents/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404
