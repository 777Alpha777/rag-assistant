# rag-assistant

[![CI](https://github.com/777Alpha777/rag-assistant/actions/workflows/ci.yml/badge.svg)](https://github.com/777Alpha777/rag-assistant/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-async-009688)
![pgvector](https://img.shields.io/badge/PostgreSQL-pgvector-336791)

Question answering over internal engineering documents: document ingestion,
**hybrid retrieval** (pgvector + PostgreSQL full-text search), answers with
citations, and a retrieval evaluation harness instead of "it feels better".

The interesting part is not the LLM call - it is what happens before it: how chunks
are built, how candidates are retrieved, and how the quality of that retrieval is
measured.

## Why it is built this way

| Problem | Solution in this repo |
|---|---|
| An answer without sources is unverifiable | Every claim carries a `[n]` marker, the API always returns the source chunks |
| A chunk quoted out of context is useless | Chunks keep a heading breadcrumb (`Deployment and rollback > Rollback`) |
| Exact terms (error codes, header names) are missed by vector search | Full-text search with an OR-tsquery, fused with the vector ranking |
| "Hybrid search is better" is an opinion | `scripts/evaluate.py` reports hit@1 / hit@3 / MRR for both retrievers |
| Re-running the indexing job duplicates the corpus | Ingest is idempotent by content checksum; an edited file replaces its chunks |
| Tests that need Docker never run locally | Tests start an embedded PostgreSQL (`pgserver`) with pgvector, no Docker required |
| The project would not run without an API key | Deterministic hash embedder and extractive answerer by default; OpenAI is one env var away |

## Architecture

```mermaid
flowchart LR
    C[Client] --> A[FastAPI]
    A --> I[Ingest service]
    I --> CH[Chunker<br/>heading breadcrumbs]
    I --> E["Embedder<br/>hash or openai"]
    I --> PG[(PostgreSQL<br/>pgvector + tsvector)]
    A --> R[Hybrid retrieval<br/>vector + full-text + RRF]
    R --> PG
    R --> L["Answerer<br/>stub or openai"]
    L --> A
    A --> M["/metrics/"]
```

Layers: `api` (HTTP contracts) -> `services` (ingest orchestration) -> `retrieval`
/ `llm` (domain logic) -> `models` (persistence). Routers stay thin, business rules
do not import HTTP types.

## Stack

- **Python 3.12**, FastAPI, Pydantic v2
- **SQLAlchemy 2.0** async + asyncpg, Alembic migrations
- **PostgreSQL 16/17** with **pgvector** (HNSW index) and `tsvector` (GIN index)
- httpx, prometheus-client
- pytest + httpx ASGI transport, ruff, GitHub Actions

## Quickstart

```bash
cp .env.example .env
docker compose up --build -d     # db (pgvector/pgvector:pg17) + api, migrations on start
```

Index the sample corpus and ask a question:

```bash
docker compose exec api python -m scripts.ingest_corpus

curl -s localhost:8001/api/v1/ask \
  -H 'content-type: application/json' \
  -d '{"question": "How long does an Idempotency-Key stay valid?"}'
```

```json
{
  "answer": "Any endpoint that creates a resource accepts an Idempotency-Key header. [1]",
  "sources": [
    {
      "title": "Api Guidelines",
      "heading": "API guidelines > Idempotency",
      "snippet": "Any endpoint that creates a resource accepts an Idempotency-Key header. The client ...",
      "score": 0.127273
    }
  ],
  "llm": "stub-extractive",
  "embedding_model": "hash-1024",
  "latency_ms": 45.05
}
```

Without Docker (any PostgreSQL with pgvector, `pip install -e ".[dev]"`):

```bash
alembic upgrade head
python -m scripts.ingest_corpus
uvicorn app.main:app --reload --port 8000
```

Docs are at `http://localhost:8000/docs`.

## API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/documents` | Ingest a document (`title`, `source`, `text`). `201` created, `200` unchanged |
| `GET` | `/api/v1/documents` | List documents with chunk counts |
| `DELETE` | `/api/v1/documents/{id}` | Delete a document and its chunks |
| `POST` | `/api/v1/ask` | Ask a question, get an answer plus ranked sources |
| `GET` | `/health` | Liveness |
| `GET` | `/metrics` | Prometheus metrics (HTTP, ingest, ask latency) |

`/ask` accepts an optional `top_k` (1..20) to override the configured context size.

## Design decisions

**Chunking keeps section context.** Markdown headings are tracked as a stack, so a
chunk knows it is `Deployment and rollback > Rollback`. Paragraphs are packed up to
`CHUNK_SIZE` characters with `CHUNK_OVERLAP` of the previous chunk repeated, so a
rule split across a boundary is still readable in one fragment. The heading is
prepended to the text before embedding: it carries meaning the paragraph may not.

**Hybrid retrieval instead of pure vectors.** Embeddings answer "what is this text
about"; they are bad at exact identifiers. Internal documentation is full of them -
`Idempotency-Key`, `Argon2`, `Severity 1`. Both retrievers run over the same table
and their ranked lists are fused with Reciprocal Rank Fusion, so no score
normalisation between cosine similarity and `ts_rank_cd` is needed.

**OR-tsquery, built in Python.** `plainto_tsquery` joins terms with AND: the question
"How long does a rollback take?" becomes `long & does & a & rollback & take` and
matches almost nothing, because documents do not contain the question, they contain
the answers. `build_tsquery` joins the tokens with OR and lets ranking sort it out.

**Weighted RRF, `RRF_K = 10`.** Standard RRF uses `k = 60`, which assumes result
lists of hundreds of items; with six candidates per list it flattens the ranking to
almost equal weights. `k = 10` keeps the order meaningful. The lexical list is
weighted `0.4` because OR-matching is noisy on a small corpus: a chunk that repeats
common words can top the lexical list while being irrelevant. Weights are a
conscious trade-off, not a claim of optimality - see the evaluation below.

**Idempotent ingest.** A document is identified by `source` and a SHA-256 of its
content. Re-ingesting an unchanged file is a no-op (`200`, `created: false`);
re-ingesting a changed file deletes the old chunks and writes new ones. Without
this, every indexing run would multiply the corpus and skew retrieval towards
whatever was indexed last.

**`lazy="raise"` on the relationship.** Serialising a document never silently
triggers a query per chunk; the API counts chunks with an explicit aggregate.
Deletion removes chunks explicitly, because an ORM cascade would need a lazy load
the mapper is configured to refuse.

## Retrieval quality (measured, not claimed)

`python -m scripts.evaluate` runs a golden set of 12 questions against the sample
corpus (5 documents, 20 chunks) and checks whether the chunk that answers the
question is in the top of the ranking, identified by its heading.

| Retriever | hit@1 | hit@3 | MRR |
|---|---|---|---|
| vector only | 75% | 92% | 0.854 |
| hybrid (vector + full-text, weighted RRF) | 75% | 100% | 0.861 |

How to read this honestly:

- Hybrid retrieval finds the right section in the top 3 for **every** question,
  vector-only misses one. For RAG that is the metric that matters: the generator
  sees all `top_k` fragments, so a hit at rank 2 still produces a correct answer.
- hit@1 does not improve, and on this corpus that is the expected result. The
  default embedder is a **hashed bag-of-words**, not a semantic model: it captures
  lexical overlap, which is exactly what the full-text side already does. With
  `EMBEDDING_PROVIDER=openai` the dense side becomes semantic and the two
  retrievers stop overlapping - the harness is there to measure that, not to
  assume it.
- 12 questions and 20 chunks is a small evaluation set. The numbers demonstrate
  the method and the direction of the change; they are not a benchmark.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5433/rag` | Database |
| `EMBEDDING_PROVIDER` | `hash` | `hash` (offline, deterministic) or `openai` |
| `EMBEDDING_DIM` | `1024` | Vector dimension; changing it requires a migration |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Used when the provider is `openai` |
| `TEXT_SEARCH_CONFIG` | `english` | PostgreSQL text search config (`simple` for mixed languages) |
| `LLM_PROVIDER` | `stub` | `stub` (extractive, no key) or `openai` |
| `LLM_MODEL` | `gpt-4o-mini` | Used when the provider is `openai` |
| `OPENAI_API_KEY` | empty | Required by the `openai` providers |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `700` / `120` | Chunking window |
| `RETRIEVAL_K` | `6` | Fragments passed to the answerer |
| `RRF_K` / `LEXICAL_WEIGHT` | `10` / `0.4` | Fusion parameters |

## Tests

```bash
pytest -q        # 20 tests, ~13s
ruff check . && ruff format --check .
```

The suite covers chunking (breadcrumbs, size limits, overlap), ingest (idempotency,
replacement, deletion), ranking (RRF fusion, provenance of candidates) and the API
end to end. Tests do not need Docker: if `TEST_DATABASE_URL` is not set, the fixture
starts `pgserver` - a pip-installable PostgreSQL with pgvector - and creates the
schema. In CI the same tests run against the `pgvector/pgvector:pg17` service
container.

## Limitations and next steps

- The extractive `stub` answerer produces one or two quoted sentences. It exists so
  the pipeline is testable and demoable without a key; the quality comes from the
  `openai` provider.
- HNSW is built with default parameters (`m=16`, `ef_construction=64`) and
  `ef_search` is untouched. With 20 chunks the index is not the bottleneck; at
  scale it should be tuned and measured.
- No reranker. A cross-encoder over the top 20 candidates is the obvious next step
  and the evaluation harness can already show whether it pays off.
- No document-level access control: every user sees the whole corpus.
- `TEXT_SEARCH_CONFIG` is fixed by migration (the `tsvector` column is generated),
  so supporting several languages means several generated columns.
