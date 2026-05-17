from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from apeiria.ai.model.adapters.openai_compatible import OpenAICompatibleProvider
from apeiria.ai.model.runtime.adapter import AIModelStreamRequest

if TYPE_CHECKING:
    from pytest import MonkeyPatch


def test_openai_stream_final_response_includes_usage(
    monkeypatch: "MonkeyPatch",
) -> None:
    import apeiria.ai.model.adapters.openai_compatible as module

    created_payloads: list[dict[str, Any]] = []

    class ChatCompletions:
        async def create(self, **payload: Any) -> Any:
            created_payloads.append(payload)
            return _AsyncChunks(
                [
                    _chunk(delta="hello "),
                    _chunk(delta="world", finish_reason="stop"),
                    _chunk(
                        choices=[],
                        usage={
                            "prompt_tokens": 9,
                            "completion_tokens": 2,
                            "total_tokens": 11,
                        },
                    ),
                ]
            )

    class Client:
        def __init__(self) -> None:
            self.chat = SimpleNamespace(
                completions=ChatCompletions(),
            )

        async def close(self) -> None:
            return None

    monkeypatch.setattr(module, "_build_openai_client", lambda **_: Client())
    provider = OpenAICompatibleProvider(
        api_base="https://example.invalid/v1",
        api_key="test-key",
    )

    events = asyncio.run(
        _collect_stream(
            provider.stream_text(
                AIModelStreamRequest(
                    source_id="source-1",
                    model_name="gpt-test",
                )
            )
        )
    )

    final = events[-1].response
    assert created_payloads[0]["stream_options"] == {"include_usage": True}
    assert final is not None
    assert final.content == "hello world"
    assert final.finish_reason == "stop"
    assert final.usage == {
        "prompt_tokens": 9,
        "completion_tokens": 2,
        "total_tokens": 11,
    }


async def _collect_stream(stream: Any) -> list[Any]:
    return [event async for event in stream]


class _AsyncChunks:
    def __init__(self, chunks: list[Any]) -> None:
        self._chunks = chunks

    def __aiter__(self) -> "_AsyncChunks":
        return self

    async def __anext__(self) -> Any:
        if not self._chunks:
            raise StopAsyncIteration
        return self._chunks.pop(0)


def _chunk(
    *,
    delta: str = "",
    finish_reason: str | None = None,
    choices: list[Any] | None = None,
    usage: dict[str, int] | None = None,
) -> Any:
    if choices is None:
        choices = [
            SimpleNamespace(
                delta=SimpleNamespace(content=delta),
                finish_reason=finish_reason,
            )
        ]
    return SimpleNamespace(
        id="chatcmpl-1",
        choices=choices,
        usage=usage,
    )
