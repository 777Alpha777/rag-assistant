"""Answer generation on top of retrieved chunks.

Two backends: a deterministic extractive stub (no key required, used in tests
and for offline demos) and a real OpenAI chat model. Both must return text with
``[n]`` markers that map back to the sources, so the API can always show what
the answer was built from.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.config import Settings

TOKEN_RE = re.compile(r"[0-9a-zA-Z_\u0400-\u04ff]+")
OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"
NO_ANSWER = "The provided documents do not contain an answer to this question."

SYSTEM_PROMPT = (
    "You answer questions using ONLY the numbered context fragments. "
    "Cite every claim with the fragment number in square brackets, for example [2]. "
    "If the context does not contain the answer, say so explicitly instead of guessing. "
    "Answer in the language of the question, in at most five sentences."
)


@dataclass(frozen=True, slots=True)
class ContextChunk:
    index: int
    title: str
    heading: str
    content: str


class Answerer(Protocol):
    @property
    def name(self) -> str: ...

    async def answer(self, question: str, context: Sequence[ContextChunk]) -> str: ...


def build_user_prompt(question: str, context: Sequence[ContextChunk]) -> str:
    blocks = "\n\n".join(
        f"[{chunk.index}] {chunk.title} — {chunk.heading}\n{chunk.content}" for chunk in context
    )
    return f"Context fragments:\n\n{blocks}\n\nQuestion: {question}"


class StubAnswerer:
    """Extractive answer: picks the sentences with the highest token overlap.

    Deterministic by construction — same question, same answer — which is what
    makes the end-to-end tests stable. It only reads the top two fragments: with
    a wider window it starts stitching together sentences that merely share a
    word with the question.
    """

    @property
    def name(self) -> str:
        return "stub-extractive"

    async def answer(self, question: str, context: Sequence[ContextChunk]) -> str:
        question_tokens = set(TOKEN_RE.findall(question.lower()))
        scored: list[tuple[float, str, int]] = []

        for chunk in context[:2]:
            for sentence in re.split(r"(?<=[.!?])\s+|\n", chunk.content):
                sentence = sentence.strip()
                if len(sentence) < 20:
                    continue
                overlap = len(set(TOKEN_RE.findall(sentence.lower())) & question_tokens)
                if overlap >= 2:
                    # Length-normalised, so a long sentence cannot win on volume.
                    scored.append((overlap / (len(sentence.split()) ** 0.5), sentence, chunk.index))

        if not scored:
            return NO_ANSWER

        scored.sort(key=lambda item: (-item[0], item[1]))
        return " ".join(f"{sentence} [{index}]" for _, sentence, index in scored[:2])


class OpenAIAnswerer:
    def __init__(self, model: str, api_key: str, timeout: float = 30.0) -> None:
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for the openai llm provider")
        self._model = model
        self._api_key = api_key
        self._timeout = timeout

    @property
    def name(self) -> str:
        return f"openai-{self._model}"

    async def answer(self, question: str, context: Sequence[ContextChunk]) -> str:
        payload = {
            "model": self._model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(question, context)},
            ],
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(OPENAI_CHAT_URL, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        return data["choices"][0]["message"]["content"].strip()


def build_answerer(settings: Settings) -> Answerer:
    if settings.llm_provider == "openai":
        return OpenAIAnswerer(
            model=settings.llm_model,
            api_key=settings.openai_api_key or "",
            timeout=settings.llm_timeout_seconds,
        )
    return StubAnswerer()
