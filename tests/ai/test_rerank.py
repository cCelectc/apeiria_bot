from __future__ import annotations


def test_rerank_result_dataclass() -> None:
    from apeiria.ai.types import RerankResult

    r = RerankResult(index=0, score=0.95, text="hello")
    assert r.index == 0
    assert r.score == 0.95  # noqa: PLR2004
    assert r.text == "hello"


def test_rerank_result_without_text() -> None:
    from apeiria.ai.types import RerankResult

    r = RerankResult(index=2, score=0.5)
    assert r.index == 2  # noqa: PLR2004
    assert r.text is None
