"""Embedding backends.

Two implementations behind one protocol:

* ``HashEmbedder`` — deterministic hashed bag-of-words. Not semantic, but it
  keeps ingest → index → retrieve → answer runnable offline and in CI, and it
  makes retrieval tests reproducible.
* ``OpenAIEmbedder`` — real embeddings via the API, used when a key is present.

Both produce ``embedding_dim`` floats so the database schema does not change
when switching providers.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from typing import Protocol

import httpx

from app.config import Settings

TOKEN_RE = re.compile(r"[0-9a-zA-Z_\u0400-\u04ff]+")
OPENAI_EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"


class Embedder(Protocol):
    @property
    def name(self) -> str: ...

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class HashEmbedder:
    @property
    def name(self) -> str:
        return f"hash-{self._dim}"

    def __init__(self, dim: int) -> None:
        if dim <= 0:
            raise ValueError("dim must be positive")
        self._dim = dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self._dim
        for token, count in Counter(TOKEN_RE.findall(text.lower())).items():
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest, "big") % self._dim
            # Sublinear term frequency: the tenth mention of a word matters less
            # than the second one.
            vector[index] += 1.0 + math.log(count)

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0.0:
            return vector
        return [value / norm for value in vector]


class OpenAIEmbedder:
    def __init__(self, model: str, dim: int, api_key: str, timeout: float = 30.0) -> None:
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for the openai embedding provider")
        self._model = model
        self._dim = dim
        self._api_key = api_key
        self._timeout = timeout

    @property
    def name(self) -> str:
        return f"openai-{self._model}"

    async def embed(self, texts: list[str]) -> list[list[float]]:
        payload = {"model": self._model, "input": texts, "dimensions": self._dim}
        headers = {"Authorization": f"Bearer {self._api_key}"}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(OPENAI_EMBEDDINGS_URL, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()["data"]

        ordered = sorted(data, key=lambda item: item["index"])
        return [item["embedding"] for item in ordered]


def build_embedder(settings: Settings) -> Embedder:
    if settings.embedding_provider == "openai":
        return OpenAIEmbedder(
            model=settings.embedding_model,
            dim=settings.embedding_dim,
            api_key=settings.openai_api_key or "",
            timeout=settings.llm_timeout_seconds,
        )
    return HashEmbedder(dim=settings.embedding_dim)
