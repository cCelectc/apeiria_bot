from __future__ import annotations

from apeiria.ai.knowledge.chunking import recursive_split


def test_short_text_single_chunk() -> None:
    text = "Short text."
    chunks = recursive_split(text)
    assert len(chunks) == 1
    assert chunks[0] == "Short text."


def test_paragraph_splitting() -> None:
    paragraphs = ["A" * 900, "B" * 900]
    text = "\n\n".join(paragraphs)
    chunks = recursive_split(text)
    assert len(chunks) >= 2  # noqa: PLR2004
    for chunk in chunks:
        assert len(chunk) <= 1200  # noqa: PLR2004


def test_long_paragraph_splits_at_sentence() -> None:
    sentences = ["这是一个测试句子。" * 120]
    text = "".join(sentences)
    chunks = recursive_split(text)
    assert len(chunks) > 1


def test_empty_text() -> None:
    chunks = recursive_split("")
    assert chunks == []


def test_force_split_no_separators() -> None:
    text = "X" * 3000
    chunks = recursive_split(text)
    assert len(chunks) >= 3  # noqa: PLR2004
    for chunk in chunks:
        assert len(chunk) <= 1200  # noqa: PLR2004
