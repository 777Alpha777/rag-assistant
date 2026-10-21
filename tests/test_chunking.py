from __future__ import annotations

import pytest

from app.chunking import split_document


def test_headings_become_breadcrumbs() -> None:
    text = "# Guide\n\nIntro paragraph.\n\n## Section\n\nBody of the section."
    chunks = split_document(text)

    assert [chunk.heading for chunk in chunks] == ["Guide", "Guide > Section"]
    assert chunks[1].content.startswith("Body of the section")


def test_chunks_respect_max_size() -> None:
    paragraph = "word " * 400
    chunks = split_document(f"# Title\n\n{paragraph}", max_chars=500, overlap=0)

    assert len(chunks) > 1
    assert all(len(chunk.content) <= 500 for chunk in chunks)


def test_ordinals_are_sequential() -> None:
    text = "\n\n".join(f"# Section {i}\n\nBody {i}." for i in range(5))
    chunks = split_document(text)

    assert [chunk.ordinal for chunk in chunks] == list(range(len(chunks)))


def test_neighbouring_chunks_overlap() -> None:
    text = "\n\n".join(f"Paragraph number {i} with enough words to fill space." for i in range(20))
    chunks = split_document(f"# Title\n\n{text}", max_chars=200, overlap=60)

    assert len(chunks) >= 3
    # Overlap means content is duplicated across chunk boundaries, so the sum of
    # chunk lengths must exceed the original text.
    assert sum(len(chunk.content) for chunk in chunks) > len(text)


def test_no_overlap_when_disabled() -> None:
    text = "\n\n".join(f"Paragraph number {i} with enough words to fill space." for i in range(20))
    chunks = split_document(f"# Title\n\n{text}", max_chars=200, overlap=0)

    assert len(chunks) >= 3
    assert sum(len(chunk.content) for chunk in chunks) <= len(text)


def test_invalid_parameters_raise() -> None:
    with pytest.raises(ValueError, match="max_chars must be positive"):
        split_document("text", max_chars=0)
    with pytest.raises(ValueError, match="overlap must be in"):
        split_document("text", max_chars=100, overlap=100)


def test_leading_text_without_heading_is_kept() -> None:
    chunks = split_document("Just a paragraph without any heading.")

    assert len(chunks) == 1
    assert chunks[0].heading == ""
