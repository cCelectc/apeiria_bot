from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, ClassVar

from apeiria.ai.model.registry import register_provider

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from apeiria.ai.types import StreamEvent


@register_provider("anthropic_compatible")
class AnthropicCompatibleProvider:
    capabilities: ClassVar[set[str]] = {"chat"}

    async def stream(
        self,
        model_id: str,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AsyncIterator[StreamEvent]:
        from anthropic import AsyncAnthropic

        from apeiria.ai.types import StreamEvent, StreamEventType

        source_config = await self._get_source_config(model_id, "ai_chat_models")
        client = AsyncAnthropic(
            api_key=source_config.get("api_key", ""),
            base_url=source_config.get("api_base"),
        )

        model_identifier = source_config.get("model_identifier", model_id)
        system_text, chat_messages = _split_system(messages)

        request_kwargs = _build_request_kwargs(
            model_identifier, chat_messages, system_text, kwargs
        )

        try:
            async with client.messages.stream(**request_kwargs) as stream:
                tool_calls_acc: dict[int, dict[str, Any]] = {}

                async for event in stream:
                    result = _handle_stream_event(event, tool_calls_acc)
                    if result:
                        yield result

                for tc_event in _emit_anthropic_tool_calls(tool_calls_acc):
                    yield tc_event

                final_message = await stream.get_final_message()
                usage_event = _extract_final_usage(final_message)
                if usage_event:
                    yield usage_event

            yield StreamEvent(type=StreamEventType.END)
        except Exception as e:  # noqa: BLE001
            _normalize_anthropic_error(e)

    async def _get_source_config(self, model_id: str, table: str) -> dict[str, Any]:
        from apeiria.ai.model.adapters.openai_compatible import (
            _resolve_source_config,
        )

        return await _resolve_source_config(model_id, table)


def _build_request_kwargs(
    model_identifier: str,
    chat_messages: list[dict[str, Any]],
    system_text: str,
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    request_kwargs: dict[str, Any] = {
        "model": model_identifier,
        "messages": chat_messages,
        "max_tokens": kwargs.get("max_tokens", 4096),
    }
    if system_text:
        request_kwargs["system"] = system_text
    if kwargs.get("tools"):
        request_kwargs["tools"] = [_convert_tool_def(t) for t in kwargs["tools"]]
    reasoning_effort = kwargs.get("reasoning_effort")
    if reasoning_effort:
        request_kwargs["thinking"] = {"type": "adaptive"}
        request_kwargs["output_config"] = {"effort": reasoning_effort}
    return request_kwargs


def _convert_tool_def(t: dict[str, Any]) -> dict[str, Any]:
    if "function" in t:
        fn = t["function"]
        return {
            "name": fn["name"],
            "description": fn.get("description", ""),
            "input_schema": fn.get("parameters", {}),
        }
    return t


def _handle_stream_event(
    event: Any,
    tool_calls_acc: dict[int, dict[str, Any]],
) -> StreamEvent | None:
    from apeiria.ai.types import StreamEvent, StreamEventType, TokenUsage

    if event.type == "content_block_start":
        if event.content_block.type == "tool_use":
            tool_calls_acc[event.index] = {
                "id": event.content_block.id,
                "name": event.content_block.name,
                "arguments": "",
            }
        return None

    if event.type == "content_block_delta":
        if event.delta.type == "text_delta":
            return StreamEvent(
                type=StreamEventType.TEXT_DELTA,
                text=event.delta.text,
            )
        if event.delta.type == "input_json_delta":
            idx = event.index
            if idx in tool_calls_acc:
                tool_calls_acc[idx]["arguments"] += event.delta.partial_json
        return None

    if event.type == "message_delta":
        usage_obj = getattr(event, "usage", None)
        if usage_obj:
            return StreamEvent(
                type=StreamEventType.USAGE,
                usage=TokenUsage(
                    prompt_tokens=getattr(usage_obj, "input_tokens", 0) or 0,
                    completion_tokens=getattr(usage_obj, "output_tokens", 0) or 0,
                ),
            )

    return None


def _emit_anthropic_tool_calls(
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


def _extract_final_usage(final_message: Any) -> StreamEvent | None:
    from apeiria.ai.types import StreamEvent, StreamEventType, TokenUsage

    usage = getattr(final_message, "usage", None)
    input_tokens = getattr(usage, "input_tokens", 0)
    output_tokens = getattr(usage, "output_tokens", 0)
    if input_tokens or output_tokens:
        return StreamEvent(
            type=StreamEventType.USAGE,
            usage=TokenUsage(
                prompt_tokens=input_tokens or 0,
                completion_tokens=output_tokens or 0,
            ),
        )
    return None


def _normalize_anthropic_error(e: Exception) -> None:
    from apeiria.ai.model.exceptions import (
        AIModelAuthError,
        AIModelConnectionError,
        AIModelContextLengthError,
        AIModelOverloadedError,
        AIModelRateLimitError,
    )

    error_str = str(e).lower()
    if "rate limit" in error_str or "429" in error_str:
        raise AIModelRateLimitError(str(e)) from e
    if "auth" in error_str or "401" in error_str or "api key" in error_str:
        raise AIModelAuthError(str(e)) from e
    context_markers = ("context length", "maximum context", "too many tokens")
    if any(s in error_str for s in context_markers):
        raise AIModelContextLengthError(str(e)) from e
    if "overloaded" in error_str or "529" in error_str:
        raise AIModelOverloadedError(str(e)) from e
    if "connection" in error_str or "timeout" in error_str:
        raise AIModelConnectionError(str(e)) from e
    raise e


def _split_system(
    messages: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    system_parts: list[str] = []
    chat: list[dict[str, Any]] = []

    for msg in messages:
        role = msg.get("role")
        if role == "system":
            content = msg.get("content", "")
            if isinstance(content, str) and content:
                system_parts.append(content)
        elif role == "tool":
            _handle_tool_message(chat, msg)
        elif role == "assistant":
            _handle_assistant_message(chat, msg)
        else:
            _append_user(chat, msg.get("content", ""))

    system_text = "\n\n".join(system_parts) if system_parts else ""
    return system_text, chat


def _handle_tool_message(chat: list[dict[str, Any]], msg: dict[str, Any]) -> None:
    tool_result_block: dict[str, Any] = {
        "type": "tool_result",
        "tool_use_id": msg.get("tool_call_id", ""),
        "content": msg.get("content", ""),
    }
    if chat and chat[-1]["role"] == "user" and isinstance(chat[-1]["content"], list):
        chat[-1]["content"].append(tool_result_block)
    else:
        chat.append({"role": "user", "content": [tool_result_block]})


def _handle_assistant_message(chat: list[dict[str, Any]], msg: dict[str, Any]) -> None:
    content_blocks: list[dict[str, Any]] = []
    text_content = msg.get("content", "")
    if isinstance(text_content, str) and text_content:
        content_blocks.append({"type": "text", "text": text_content})
    tool_calls = msg.get("tool_calls")
    if isinstance(tool_calls, list):
        for tc in tool_calls:
            fn = tc.get("function", {})
            arguments = fn.get("arguments", "{}")
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    arguments = {}
            content_blocks.append(
                {
                    "type": "tool_use",
                    "id": tc.get("id", ""),
                    "name": fn.get("name", ""),
                    "input": arguments,
                }
            )
    chat.append(
        {
            "role": "assistant",
            "content": content_blocks or [{"type": "text", "text": ""}],
        }
    )


def _append_user(
    chat: list[dict[str, Any]], content: str | list[dict[str, Any]]
) -> None:
    if chat and chat[-1]["role"] == "user":
        prev = chat[-1]["content"]
        if isinstance(prev, str) and isinstance(content, str):
            chat[-1]["content"] = f"{prev}\n{content}"
        elif isinstance(prev, str):
            chat[-1]["content"] = [{"type": "text", "text": prev}, *content]
        elif isinstance(prev, list) and isinstance(content, str):
            prev.append({"type": "text", "text": content})
        elif isinstance(prev, list) and isinstance(content, list):
            prev.extend(content)
    else:
        chat.append({"role": "user", "content": content})
