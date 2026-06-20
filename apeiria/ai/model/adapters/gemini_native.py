from __future__ import annotations

import json
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, ClassVar
from urllib.parse import quote

import httpx

from apeiria.ai.model.registry import register_provider

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from apeiria.ai.types import StreamEvent

_DEFAULT_TIMEOUT_SECONDS = 120


@register_provider("gemini_native")
class GeminiNativeProvider:
    capabilities: ClassVar[set[str]] = {"chat"}

    async def stream(
        self,
        model_id: str,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AsyncIterator[StreamEvent]:
        from apeiria.ai.types import StreamEvent, StreamEventType, TokenUsage

        source_config = await self._get_source_config(model_id, "ai_chat_models")
        api_base = source_config.get(
            "api_base", "https://generativelanguage.googleapis.com/v1beta"
        )
        api_key = source_config.get("api_key", "")
        model_identifier = source_config.get("model_identifier", model_id)

        model_path = quote(_strip_model_prefix(model_identifier), safe="")
        url = (
            f"{api_base.rstrip('/')}/models/{model_path}:streamGenerateContent?alt=sse"
        )

        payload = _build_gemini_payload(messages, kwargs.get("tools"))
        headers = {"x-goog-api-key": api_key}

        try:
            tool_calls_collected: list[dict[str, Any]] = []
            usage_data: dict[str, int] = {}

            async with (
                httpx.AsyncClient(
                    timeout=float(_DEFAULT_TIMEOUT_SECONDS),
                ) as client,
                client.stream("POST", url, headers=headers, json=payload) as response,
            ):
                if response.status_code >= HTTPStatus.BAD_REQUEST:
                    body = await response.aread()
                    _raise_gemini_error(
                        response.status_code,
                        body.decode(errors="replace"),
                    )

                async for line in response.aiter_lines():
                    chunk = _parse_sse_line(line)
                    if chunk is None:
                        continue
                    text_events, new_tool_calls = _extract_chunk_data(chunk)
                    for text in text_events:
                        yield StreamEvent(type=StreamEventType.TEXT_DELTA, text=text)
                    tool_calls_collected.extend(new_tool_calls)
                    usage_meta = chunk.get("usageMetadata")
                    if isinstance(usage_meta, dict):
                        usage_data = _extract_usage_meta(usage_meta)

            for tc_event in _emit_gemini_tool_calls(tool_calls_collected):
                yield tc_event

            if usage_data:
                yield StreamEvent(
                    type=StreamEventType.USAGE,
                    usage=TokenUsage(
                        prompt_tokens=usage_data.get("prompt_tokens", 0),
                        completion_tokens=usage_data.get("completion_tokens", 0),
                    ),
                )

            yield StreamEvent(type=StreamEventType.END)
        except Exception as e:  # noqa: BLE001
            _normalize_gemini_error(e)

    async def _get_source_config(self, model_id: str, table: str) -> dict[str, Any]:
        from apeiria.ai.model.adapters.openai_compatible import (
            _resolve_source_config,
        )

        return await _resolve_source_config(model_id, table)


def _strip_model_prefix(model_name: str) -> str:
    return model_name.strip().removeprefix("models/")


def _parse_sse_line(line: str) -> dict[str, Any] | None:
    if not line.startswith("data: "):
        return None
    try:
        return json.loads(line[6:])
    except json.JSONDecodeError:
        return None


def _extract_chunk_data(
    chunk: dict[str, Any],
) -> tuple[list[str], list[dict[str, Any]]]:
    texts: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    for candidate in chunk.get("candidates", []):
        content = candidate.get("content", {})
        for part in content.get("parts", []):
            text = part.get("text")
            if text:
                texts.append(text)
            fc = part.get("functionCall")
            if fc:
                tool_calls.append(
                    {"name": fc.get("name", ""), "arguments": fc.get("args", {})}
                )
    return texts, tool_calls


def _extract_usage_meta(usage_meta: dict[str, Any]) -> dict[str, int]:
    return {
        "prompt_tokens": usage_meta.get("promptTokenCount", 0),
        "completion_tokens": usage_meta.get("candidatesTokenCount", 0),
    }


def _emit_gemini_tool_calls(
    collected: list[dict[str, Any]],
) -> list[StreamEvent]:
    from apeiria.ai.types import StreamEvent, StreamEventType, ToolCall

    events: list[StreamEvent] = []
    for i, tc_data in enumerate(collected):
        events.append(
            StreamEvent(
                type=StreamEventType.TOOL_CALL_END,
                tool_call=ToolCall(
                    id=f"gemini_tc_{i}",
                    name=tc_data["name"],
                    arguments=tc_data["arguments"]
                    if isinstance(tc_data["arguments"], dict)
                    else {},
                ),
            )
        )
    return events


def _raise_gemini_error(status_code: int, body: str) -> None:
    from apeiria.ai.model.exceptions import (
        AIModelAuthError,
        AIModelRateLimitError,
    )

    lower = body.lower()
    if status_code == HTTPStatus.TOO_MANY_REQUESTS or "rate limit" in lower:
        raise AIModelRateLimitError(body[:500])
    if (
        status_code in {HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN}
        or "api key" in lower
    ):
        raise AIModelAuthError(body[:500])
    msg = f"Gemini API error {status_code}: {body[:500]}"
    raise RuntimeError(msg)


def _normalize_gemini_error(e: Exception) -> None:
    from apeiria.ai.model.exceptions import (
        AIModelAuthError,
        AIModelConnectionError,
        AIModelContextLengthError,
        AIModelRateLimitError,
    )

    if isinstance(
        e,
        (
            AIModelRateLimitError,
            AIModelAuthError,
            AIModelContextLengthError,
            AIModelConnectionError,
        ),
    ):
        raise e
    error_str = str(e).lower()
    if "rate limit" in error_str or "429" in error_str:
        raise AIModelRateLimitError(str(e)) from e
    if "api key" in error_str or "401" in error_str or "403" in error_str:
        raise AIModelAuthError(str(e)) from e
    if "context length" in error_str or "token limit" in error_str:
        raise AIModelContextLengthError(str(e)) from e
    if "connection" in error_str or "timeout" in error_str:
        raise AIModelConnectionError(str(e)) from e
    raise e


def _build_gemini_payload(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    system_parts: list[str] = []
    contents: list[dict[str, Any]] = []

    for msg in messages:
        role = msg.get("role", "user")
        if role == "system":
            content = msg.get("content", "")
            if isinstance(content, str) and content:
                system_parts.append(content)
            continue
        entry = _build_gemini_content_entry(msg, role)
        if entry:
            contents.append(entry)

    payload: dict[str, Any] = {
        "contents": contents or [{"role": "user", "parts": [{"text": ""}]}],
    }
    if system_parts:
        payload["systemInstruction"] = {"parts": [{"text": "\n\n".join(system_parts)}]}
    if tools:
        func_declarations = _build_func_declarations(tools)
        if func_declarations:
            payload["tools"] = [{"functionDeclarations": func_declarations}]

    return payload


def _build_gemini_content_entry(
    msg: dict[str, Any], role: str
) -> dict[str, Any] | None:
    content = msg.get("content", "")
    gemini_role = "model" if role == "assistant" else "user"
    parts: list[dict[str, Any]] = []

    if role == "tool":
        return {
            "role": "user",
            "parts": [
                {
                    "functionResponse": {
                        "name": msg.get("name", ""),
                        "response": {"result": content},
                    }
                }
            ],
        }

    if isinstance(content, str) and content:
        parts.append({"text": content})
    elif isinstance(content, list):
        parts.extend(
            {"text": block.get("text", "")}
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )

    tool_calls = msg.get("tool_calls")
    if isinstance(tool_calls, list):
        parts.extend(_build_function_call_part(tc) for tc in tool_calls)

    if parts:
        return {"role": gemini_role, "parts": parts}
    return None


def _build_function_call_part(tc: dict[str, Any]) -> dict[str, Any]:
    fn = tc.get("function", {})
    arguments = fn.get("arguments", "{}")
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            arguments = {}
    return {"functionCall": {"name": fn.get("name", ""), "args": arguments}}


def _build_func_declarations(
    tools: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    declarations: list[dict[str, Any]] = []
    for tool in tools:
        if "function" in tool:
            fn = tool["function"]
            declarations.append(
                {
                    "name": fn.get("name", ""),
                    "description": fn.get("description", ""),
                    "parameters": fn.get("parameters", {}),
                }
            )
    return declarations
