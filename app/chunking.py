"""Split markdown into chunks that keep their section context.

The goal is not "nice chunks" but retrievable ones: every chunk carries the
heading breadcrumb it came from, so an answer can say
"Deployment > Rollback" instead of quoting an anonymous paragraph.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True, slots=True)
class Chunk:
    ordinal: int
    heading: str
    content: str


def split_document(text: str, max_chars: int = 700, overlap: int = 120) -> list[Chunk]:
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    if overlap < 0 or overlap >= max_chars:
        raise ValueError("overlap must be in [0, max_chars)")

    chunks: list[Chunk] = []
    for heading, body in _sections(text):
        for piece in _pack(body, max_chars, overlap):
            chunks.append(Chunk(ordinal=len(chunks), heading=heading, content=piece))
    return chunks


def _sections(text: str) -> list[tuple[str, str]]:
    stack: list[tuple[int, str]] = []
    sections: list[tuple[str, list[str]]] = []
    current: list[str] | None = None

    for line in text.splitlines():
        match = HEADING_RE.match(line)
        if match:
            level, title = len(match.group(1)), match.group(2).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
            current = [" > ".join(name for _, name in stack), []]
            sections.append(current)
        else:
            if current is None:
                current = ["", []]
                sections.append(current)
            current[1].append(line)

    result: list[tuple[str, str]] = []
    for heading, lines in sections:
        body = "\n".join(lines).strip()
        if body:
            result.append((heading, body))
    return result


def _pack(body: str, max_chars: int, overlap: int) -> list[str]:
    units: list[str] = []
    for paragraph in re.split(r"\n\s*\n", body):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if len(paragraph) <= max_chars:
            units.append(paragraph)
        else:
            units.extend(_split_long(paragraph, max_chars))

    chunks: list[str] = []
    buffer = ""
    for unit in units:
        candidate = f"{buffer}\n\n{unit}" if buffer else unit
        if len(candidate) <= max_chars:
            buffer = candidate
            continue

        if buffer:
            chunks.append(buffer)
            tail = buffer[-overlap:] if overlap else ""
            buffer = f"{tail}\n\n{unit}".strip() if tail else unit
        else:
            buffer = unit

    if buffer:
        chunks.append(buffer)
    return chunks


def _split_long(text: str, max_chars: int) -> list[str]:
    out: list[str] = []
    buffer = ""
    for sentence in SENTENCE_RE.split(text):
        if len(sentence) > max_chars:
            if buffer:
                out.append(buffer)
                buffer = ""
            out.extend(sentence[i : i + max_chars] for i in range(0, len(sentence), max_chars))
            continue

        candidate = f"{buffer} {sentence}".strip() if buffer else sentence
        if len(candidate) <= max_chars:
            buffer = candidate
        else:
            out.append(buffer)
            buffer = sentence

    if buffer:
        out.append(buffer)
    return out
