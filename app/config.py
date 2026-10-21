from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5433/rag"

    # Retrieval
    embedding_provider: Literal["hash", "openai"] = "hash"
    embedding_dim: int = 1024
    embedding_model: str = "text-embedding-3-small"
    text_search_config: str = "english"
    retrieval_k: int = 6
    candidate_k: int = 30
    rrf_k: int = 10
    lexical_weight: float = 0.4

    # Generation
    llm_provider: Literal["stub", "openai"] = "stub"
    llm_model: str = "gpt-4o-mini"
    llm_timeout_seconds: float = 30.0
    openai_api_key: str | None = None

    # Chunking
    chunk_size: int = 700
    chunk_overlap: int = 120


@lru_cache
def get_settings() -> Settings:
    return Settings()
