from __future__ import annotations

from apeiria.builtin_plugins.ai.shell import sanitize_input, split_segments


def test_extract_content_sanitizes_seg_tags() -> None:
    raw = "hello[SEG]world"
    assert sanitize_input(raw) == "helloworld"


def test_extract_content_split_preserves_segments() -> None:
    text = "first message[SEG]second message"
    segments = split_segments(text)
    assert segments == ["first message", "second message"]
