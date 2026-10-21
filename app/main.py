from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.api import routes_ask, routes_documents, routes_health
from app.db import engine
from app.metrics import setup_metrics


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="RAG Assistant",
        version="0.1.0",
        description="Question answering over internal documents with hybrid retrieval.",
        lifespan=lifespan,
    )

    setup_metrics(app)

    app.include_router(routes_health.router)
    app.include_router(routes_documents.router, prefix="/api/v1")
    app.include_router(routes_ask.router, prefix="/api/v1")

    @app.exception_handler(ValueError)
    async def value_error_handler(_: Request, exc: ValueError) -> JSONResponse:
        # Domain validation (e.g. a document that produces no chunks) is a 400,
        # not a 500.
        return JSONResponse(
            status_code=400,
            content={"detail": {"type": "ValueError", "message": str(exc)}},
        )

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()
