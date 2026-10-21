import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from prometheus_client import Counter, Histogram

HTTP_REQUESTS = Counter(
    "rag_http_requests_total",
    "HTTP requests by route and status",
    ["method", "path", "status"],
)

HTTP_LATENCY = Histogram(
    "rag_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "path"],
    buckets=(0.005, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

DOCUMENTS_INGESTED = Counter(
    "rag_documents_ingested_total",
    "Documents ingested, split by whether chunks were (re)written",
    ["created"],
)

CHUNKS_INDEXED = Counter("rag_chunks_indexed_total", "Chunks written to the vector store")

ASK_TOTAL = Counter("rag_ask_total", "Questions answered", ["llm", "answered"])

ASK_LATENCY = Histogram(
    "rag_ask_latency_seconds",
    "End-to-end /ask latency (retrieval + generation)",
    ["llm"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0),
)

SOURCES_RETURNED = Histogram(
    "rag_sources_returned",
    "Number of sources attached to an answer",
    buckets=(0, 1, 2, 3, 4, 5, 6, 8, 10),
)


def setup_metrics(app: FastAPI) -> None:
    @app.middleware("http")
    async def _track(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        started = time.perf_counter()
        response = await call_next(request)

        route = request.scope.get("route")
        path = getattr(route, "path", request.url.path)
        HTTP_LATENCY.labels(request.method, path).observe(time.perf_counter() - started)
        HTTP_REQUESTS.labels(request.method, path, str(response.status_code)).inc()
        return response
