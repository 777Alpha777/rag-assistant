"""Retrieval quality: vector-only vs hybrid.

The point of this script is to answer "is the hybrid retriever actually better,
or did it just feel better". It runs the same golden question set through both
retrievers and reports hit@1, hit@3 and MRR (mean reciprocal rank).

A hit means: the chunk that answers the question is among the top-k results,
identified by the heading it belongs to.

Usage:
    python -m scripts.evaluate
"""

from __future__ import annotations

import asyncio

from app.config import get_settings
from app.db import SessionFactory, engine
from app.embeddings import build_embedder
from app.retrieval import hybrid_search, vector_search

# (question, substring of the heading that must be retrieved)
GOLDEN: list[tuple[str, str]] = [
    ("How fast must the primary on-call engineer acknowledge a page?", "On-call rotation"),
    ("What is the target rollback time for a service?", "Rollback"),
    ("How long are application logs kept?", "Retention periods"),
    ("How long does an Idempotency-Key stay valid?", "Idempotency"),
    ("Who approves write access to production?", "Production access"),
    ("When are Friday deploys allowed?", "Deployment pipeline"),
    ("Within how many days must a deletion request be completed?", "Deletion requests"),
    ("What does Severity 1 mean?", "Severity levels"),
    ("How often is access reviewed?", "Accounts"),
    ("Which pagination style is preferred for frequently changing collections?", "Pagination"),
    ("What happens to accounts of people who left the company?", "Accounts"),
    ("Are destructive migrations allowed?", "Database migrations"),
]


async def evaluate() -> None:
    settings = get_settings()
    embedder = build_embedder(settings)

    results: dict[str, dict[str, float]] = {}

    async with SessionFactory() as session:
        for mode in ("vector", "hybrid"):
            hit1 = hit3 = 0
            reciprocal_ranks: list[float] = []
            misses: list[str] = []

            for question, expected_heading in GOLDEN:
                embedding = (await embedder.embed([question]))[0]
                chunks = (
                    await vector_search(session, embedding, settings.retrieval_k)
                    if mode == "vector"
                    else await hybrid_search(session, question, embedding, settings)
                )

                rank = next(
                    (
                        position
                        for position, chunk in enumerate(chunks, start=1)
                        if expected_heading.lower() in chunk.heading.lower()
                    ),
                    None,
                )

                if rank == 1:
                    hit1 += 1
                if rank is not None and rank <= 3:
                    hit3 += 1
                else:
                    misses.append(f"{question} (expected: {expected_heading})")
                reciprocal_ranks.append(1.0 / rank if rank else 0.0)

            total = len(GOLDEN)
            results[mode] = {
                "hit@1": hit1 / total,
                "hit@3": hit3 / total,
                "mrr": sum(reciprocal_ranks) / total,
            }
            if misses:
                print(f"\n[{mode}] missed:")
                for miss in misses:
                    print(f"  - {miss}")

    await engine.dispose()

    print(
        f"\nRunning the golden question set: {len(GOLDEN)} questions, "
        f"top-k = {settings.retrieval_k}\n"
    )
    print("| Retriever | hit@1 | hit@3 | MRR |")
    print("|---|---|---|---|")
    for mode, metrics in results.items():
        print(
            f"| {mode} | {metrics['hit@1']:.0%} | {metrics['hit@3']:.0%} | {metrics['mrr']:.3f} |"
        )


if __name__ == "__main__":
    asyncio.run(evaluate())
