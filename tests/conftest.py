from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import nonebot
import pytest
from nonebot.matcher import matchers
from nonebug import App
from nonebug.provider import NoneBugProvider

from apeiria.ai.types import (
    StreamEvent,
    StreamEventType,
    TokenUsage,
    ToolCall,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Generator


def pytest_configure(config: pytest.Config) -> None:
    del config
    nonebot.init(
        command_start={"/", "!"},
        superusers=set(),
        localstore_cache_dir=Path("/tmp/apeiria-test-localstore/cache"),
        localstore_config_dir=Path("/tmp/apeiria-test-localstore/config"),
        localstore_data_dir=Path("/tmp/apeiria-test-localstore/data"),
    )
    matchers.set_provider(NoneBugProvider)


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(name="app")
def nonebug_app() -> Generator[App, None, None]:
    matchers.clear()
    yield App()
    matchers.clear()


@pytest.fixture()
def mock_llm_stream() -> _MockLLMStreamFactory:
    return _MockLLMStreamFactory()


class _MockLLMStreamFactory:
    def text(
        self,
        content: str,
        *,
        prompt_tokens: int = 100,
        completion_tokens: int = 50,
    ) -> _MockStream:
        events = [
            StreamEvent(type=StreamEventType.TEXT_DELTA, text=content),
            StreamEvent(
                type=StreamEventType.USAGE,
                usage=TokenUsage(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                ),
            ),
            StreamEvent(type=StreamEventType.END),
        ]
        return _MockStream(events)

    def tool_call(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        *,
        call_id: str = "call_1",
    ) -> _MockStream:
        events = [
            StreamEvent(
                type=StreamEventType.TOOL_CALL_END,
                tool_call=ToolCall(
                    id=call_id,
                    name=name,
                    arguments=arguments or {},
                ),
            ),
            StreamEvent(type=StreamEventType.END),
        ]
        return _MockStream(events)

    def empty(self) -> _MockStream:
        return _MockStream([StreamEvent(type=StreamEventType.END)])


class _MockStream:
    def __init__(self, events: list[StreamEvent]) -> None:
        self._events = events

    async def __call__(self, *_args: Any, **_kwargs: Any) -> AsyncIterator[StreamEvent]:
        for event in self._events:
            yield event
