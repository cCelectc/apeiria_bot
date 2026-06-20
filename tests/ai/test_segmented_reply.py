from __future__ import annotations

from apeiria.builtin_plugins.ai.shell import (
    StreamingSegmentBuffer,
    sanitize_input,
    split_segments,
    strip_seg_tags,
)


def test_split_segments() -> None:
    assert split_segments("A[SEG]B[SEG]C") == ["A", "B", "C"]


def test_split_no_tags() -> None:
    assert split_segments("plain text") == ["plain text"]


def test_split_empty_segments() -> None:
    assert split_segments("[SEG][SEG]") == []
    assert split_segments("[SEG]A[SEG]") == ["A"]


def test_strip_tags() -> None:
    assert strip_seg_tags("A[SEG]B") == "AB"


def test_sanitize_input() -> None:
    assert sanitize_input("hello[SEG]world") == "helloworld"


def test_streaming_buffer() -> None:
    buf = StreamingSegmentBuffer()
    result = buf.feed("Hello[SEG]World")
    assert result == ["Hello"]
    final = buf.flush()
    assert final == "World"


def test_streaming_partial_tag() -> None:
    buf = StreamingSegmentBuffer()
    result = buf.feed("Hello[SE")
    assert result == []
    assert buf.has_partial_tag()
    result = buf.feed("G]World")
    assert result == ["Hello"]
    final = buf.flush()
    assert final == "World"


def test_disabled_mode() -> None:
    assert strip_seg_tags("A[SEG]B[SEG]C") == "ABC"


def test_split_segments_whitespace_only() -> None:
    assert split_segments("") == []
    assert split_segments("   ") == []


def test_streaming_buffer_no_tag() -> None:
    buf = StreamingSegmentBuffer()
    result = buf.feed("plain text no tags")
    assert result == []
    final = buf.flush()
    assert final == "plain text no tags"
