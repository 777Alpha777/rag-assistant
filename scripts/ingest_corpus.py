"""Ingest everything under data/corpus into the vector store.

Usage:
    python -m scripts.ingest_corpus
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from app.config import get_settings
from app.db import SessionFactory, engine
from app.embeddings import build_embedder
from app.services.ingest import ingest_document

CORPUS_DIR = Path(__file__).resolve().parent.parent / "data" / "corpus"


async def main() -> None:
    settings = get_settings()
    embedder = build_embedder(settings)
    files = sorted(CORPUS_DIR.rglob("*.md"))

    if not files:
        raise SystemExit(f"no markdown files found in {CORPUS_DIR}")

    async with SessionFactory() as session:
        for path in files:
            title = path.stem.replace("-", " ").title()
            outcome = await ingest_document(
                session,
                embedder,
                settings,
                title=title,
                source=str(path.relative_to(CORPUS_DIR)).replace("\\", "/"),
                text=path.read_text(encoding="utf-8"),
            )
            state = "created" if outcome.created else "unchanged"
            print(f"{state:>9}  {outcome.chunk_count:>3} chunks  {path.name}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
