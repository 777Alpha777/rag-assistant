from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import get_session
from app.embeddings import Embedder, build_embedder
from app.llm import Answerer, build_answerer

SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


@lru_cache
def _embedder() -> Embedder:
    return build_embedder(get_settings())


@lru_cache
def _answerer() -> Answerer:
    return build_answerer(get_settings())


EmbedderDep = Annotated[Embedder, Depends(_embedder)]
AnswererDep = Annotated[Answerer, Depends(_answerer)]
