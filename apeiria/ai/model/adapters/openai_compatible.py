from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, ClassVar

from apeiria.ai.model.registry import register_provider

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from apeiria.ai.types import StreamEvent


@register_provider("openai_compatible")
class OpenAICompatibleProvider:
    capabilities: ClassVar[set[str]] = {"chat", "embedding"}

    async def stream(
        self,
        model_id: str,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AsyncIterator[StreamEvent]:
        from openai import AsyncOpenAI

        from apeiria.ai.types import StreamEvent, StreamEventType, TokenUsage

        source_config = await self._get_source_config(model_id, "ai_chat_models")
        client = AsyncOpenAI(
            api_key=source_config.get("api_key", ""),
            base_url=source_config.get("api_base"),
        )

        model_identifier = source_config.get("model_identifier", model_id)

        request_kwargs: dict[str, Any] = {
            "model": model_identifier,
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if kwargs.get("tools"):
            request_kwargs["tools"] = kwargs["tools"]

        try:
            response = await client.chat.completions.create(**request_kwargs)
            tool_calls_acc: dict[int, dict[str, Any]] = {}

            async for chunk in response:
                choice = chunk.choices[0] if chunk.choices else None
                if choice and choice.delta:
                    delta = choice.delta
                    if delta.content:
                        yield StreamEvent(
                            type=StreamEventType.TEXT_DELTA, text=delta.content
                        )
                    if delta.tool_calls:
                        _accumulate_tool_calls(delta.tool_calls, tool_calls_acc)

                if chunk.usage:
                    yield StreamEvent(
                        type=StreamEventType.USAGE,
                        usage=TokenUsage(
                            prompt_tokens=chunk.usage.prompt_tokens or 0,
                            completion_tokens=chunk.usage.completion_tokens or 0,
                        ),
                    )

            for tc_event in _emit_tool_calls(tool_calls_acc):
                yield tc_event
            yield StreamEvent(type=StreamEventType.END)
        except Exception as e:  # noqa: BLE001
            _normalize_openai_error(e)

    async def embed(
        self,
        model_id: str,
        texts: list[str],
    ) -> list[list[float]]:
        from openai import AsyncOpenAI

        source_config = await self._get_source_config(model_id, "ai_embedding_models")
        client = AsyncOpenAI(
            api_key=source_config.get("api_key", ""),
            base_url=source_config.get("api_base"),
        )
        model_identifier = source_config.get("model_identifier", model_id)
        response = await client.embeddings.create(model=model_identifier, input=texts)
        return [item.embedding for item in response.data]

    async def _get_source_config(self, model_id: str, table: str) -> dict[str, Any]:
        return await _resolve_source_config(model_id, table)


def _accumulate_tool_calls(deltas: Any, acc: dict[int, dict[str, Any]]) -> None:
    for tc in deltas:
        idx = tc.index
        if idx not in acc:
            acc[idx] = {"id": tc.id or "", "name": "", "arguments": ""}
        if tc.id:
            acc[idx]["id"] = tc.id
        if tc.function:
            if tc.function.name:
                acc[idx]["name"] = tc.function.name
            if tc.function.arguments:
                acc[idx]["arguments"] += tc.function.arguments


def _emit_tool_calls(
    acc: dict[int, dict[str, Any]],
) -> list[StreamEvent]:
    from apeiria.ai.types import StreamEvent, StreamEventType, ToolCall

    events: list[StreamEvent] = []
    for tc_data in acc.values():
        try:
            args = json.loads(tc_data["arguments"]) if tc_data["arguments"] else {}
        except json.JSONDecodeError:
            args = {}
        events.append(
            StreamEvent(
                type=StreamEventType.TOOL_CALL_END,
                tool_call=ToolCall(
                    id=tc_data["id"],
                    name=tc_data["name"],
                    arguments=args,
                ),
            )
        )
    return events


def _normalize_openai_error(e: Exception) -> None:
    from apeiria.ai.model.exceptions import (
        AIModelAuthError,
        AIModelConnectionError,
        AIModelContextLengthError,
        AIModelRateLimitError,
    )

    error_str = str(e).lower()
    if "rate limit" in error_str or "429" in error_str:
        raise AIModelRateLimitError(str(e)) from e
    if "auth" in error_str or "401" in error_str or "api key" in error_str:
        raise AIModelAuthError(str(e)) from e
    if "context length" in error_str or "maximum context" in error_str:
        raise AIModelContextLengthError(str(e)) from e
    if "connection" in error_str or "timeout" in error_str:
        raise AIModelConnectionError(str(e)) from e
    raise e


async def _resolve_source_config(model_id: str, table: str) -> dict[str, Any]:
    import os

    from sqlalchemy import text as sa_text

    from apeiria.db.engine import get_session

    async with get_session() as session:
        row = (
            await session.execute(
                sa_text(
                    f"SELECT source_id, model_identifier FROM {table}"
                    " WHERE model_id = :mid"
                ),
                {"mid": model_id},
            )
        ).first()
        if not row:
            return {"model_identifier": model_id}
        source_id, model_identifier = row

        source = (
            await session.execute(
                sa_text(
                    "SELECT api_base, api_key_env, extra_config_json"
                    " FROM ai_sources WHERE source_id = :sid"
                ),
                {"sid": source_id},
            )
        ).first()
        if not source:
            return {"model_identifier": model_identifier}

        api_key = os.environ.get(source[1], "") if source[1] else ""
        return {
            "api_base": source[0],
            "api_key": api_key,
            "model_identifier": model_identifier,
        }
