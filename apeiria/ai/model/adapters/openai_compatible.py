"""OpenAI-compatible source adapter."""

from __future__ import annotations

import base64
import json
import re
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import httpx
from openai import AsyncOpenAI

from apeiria.ai.model.adapters._common import (
    _coerce_custom_headers,
    _coerce_float,
    _coerce_int,
    _coerce_str,
    _unsupported_part_text,
)
from apeiria.ai.model.runtime.adapter import (
    AIModelCatalogItem,
    AIModelEmbeddingRequest,
    AIModelEmbeddingResponse,
    AIModelGenerateRequest,
    AIModelGenerateResponse,
    AIModelMessage,
    AIModelRerankRequest,
    AIModelRerankResponse,
    AIModelSpeechRequest,
    AIModelSpeechResponse,
    AIModelStreamEvent,
    AIModelStreamRequest,
    AIModelToolCall,
    AIModelTranscriptionRequest,
    AIModelTranscriptionResponse,
)
from apeiria.ai.model.runtime.capabilities import (
    AI_MODEL_REASONING_EFFORT_OPTION,
    AI_MODEL_RESPONSE_FORMAT_OPTION,
    normalize_reasoning_effort,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class OpenAICompatibleProviderConfigError(RuntimeError):
    """Raised when required OpenAI-compatible settings are missing."""

    def __init__(self, field_name: str) -> None:
        super().__init__(f"openai-compatible source requires {field_name}")


class OpenAICompatibleProviderCapabilityError(RuntimeError):
    """Raised when a capability is unsupported by the OpenAI-compatible adapter."""

    def __init__(self, capability: str) -> None:
        super().__init__(f"openai-compatible source does not support {capability}")


class OpenAICompatibleProvider:
    """OpenAI-compatible text generation adapter backed by the official SDK."""

    def __init__(  # noqa: PLR0913
        self,
        *,
        api_base: str | None,
        api_key: str | None = None,
        timeout_seconds: int | None = None,
        extra_config: dict[str, Any] | None = None,
        request_func: Any | None = None,
        list_request_func: Any | None = None,
    ) -> None:
        self.api_base = _normalize_openai_api_base(api_base)
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.extra_config = extra_config or {}
        self._request_func = request_func
        self._list_request_func = list_request_func

    async def generate_text(
        self,
        request: AIModelGenerateRequest,
    ) -> AIModelGenerateResponse:
        api_base = _coerce_str(request.extra, "api_base") or self.api_base
        api_key = _coerce_str(request.extra, "api_key") or self.api_key
        if not api_base:
            raise OpenAICompatibleProviderConfigError("api_base")
        if not api_key:
            raise OpenAICompatibleProviderConfigError("api_key")

        payload = _build_openai_chat_payload(
            model_name=request.model_name,
            prompt=request.prompt,
            messages=request.messages,
            tools=request.tools,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            options=request.options or request.extra or {},
        )
        client = _build_openai_client(
            api_key=api_key,
            api_base=api_base,
            timeout_seconds=self.timeout_seconds,
            extra_config=self.extra_config,
        )
        try:
            response = await client.chat.completions.create(**payload)
        finally:
            await client.close()
        raw = response.model_dump(mode="json")
        return AIModelGenerateResponse(
            source_id=request.source_id,
            model_name=request.model_name,
            content=_extract_openai_content(response),
            tool_calls=tuple(_extract_openai_tool_calls(response)),
            raw=raw,
            usage=raw.get("usage") if isinstance(raw.get("usage"), dict) else None,
            finish_reason=_extract_openai_finish_reason(response),
            response_id=str(raw.get("id")) if raw.get("id") is not None else None,
            reasoning_content=_extract_openai_reasoning_content(response),
            provider_data=_extract_openai_provider_data(raw),
        ).with_sanitized_visible_text()

    def stream_text(
        self,
        request: AIModelStreamRequest,
    ) -> "AsyncIterator[AIModelStreamEvent]":
        api_base = _coerce_str(request.extra, "api_base") or self.api_base
        api_key = _coerce_str(request.extra, "api_key") or self.api_key
        if not api_base:
            raise OpenAICompatibleProviderConfigError("api_base")
        if not api_key:
            raise OpenAICompatibleProviderConfigError("api_key")

        payload = _build_openai_chat_payload(
            model_name=request.model_name,
            prompt=request.prompt,
            messages=request.messages,
            tools=request.tools,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            options=request.options or request.extra or {},
        )
        payload["stream"] = True
        payload["stream_options"] = {"include_usage": True}
        client = _build_openai_client(
            api_key=api_key,
            api_base=api_base,
            timeout_seconds=self.timeout_seconds,
            extra_config=self.extra_config,
        )
        stream_id = f"stream_{uuid4().hex}"
        raw_content_parts: list[str] = []
        visible_content_parts: list[str] = []
        finish_reason: str | None = None
        response_id: str | None = None
        usage: dict[str, Any] | None = None
        think_filter = _ThinkTagStreamFilter()

        async def _stream() -> "AsyncIterator[AIModelStreamEvent]":
            nonlocal finish_reason, response_id, usage
            try:
                stream = await client.chat.completions.create(**payload)
                yield AIModelStreamEvent.start(
                    source_id=request.source_id,
                    model_name=request.model_name,
                    stream_id=stream_id,
                )
                async for chunk in stream:
                    response_id = (
                        _extract_openai_stream_response_id(chunk) or response_id
                    )
                    delta = _extract_openai_stream_delta(chunk)
                    if delta:
                        raw_content_parts.append(delta)
                        visible_delta = think_filter.feed(delta)
                        if visible_delta:
                            visible_content_parts.append(visible_delta)
                            yield AIModelStreamEvent.text_delta(
                                source_id=request.source_id,
                                model_name=request.model_name,
                                stream_id=stream_id,
                                content_delta=visible_delta,
                            )
                    finish_reason = (
                        _extract_openai_stream_finish_reason(chunk) or finish_reason
                    )
                    usage = _extract_openai_stream_usage(chunk) or usage
            except Exception as exc:  # noqa: BLE001
                yield AIModelStreamEvent.failure(
                    source_id=request.source_id,
                    model_name=request.model_name,
                    stream_id=stream_id,
                    reason="provider_stream_error",
                    diagnostic=str(exc)[:200],
                )
                return
            finally:
                await client.close()

            content = "".join(raw_content_parts)
            final_response = AIModelGenerateResponse(
                source_id=request.source_id,
                model_name=request.model_name,
                content=content,
                usage=usage,
                finish_reason=finish_reason,
                response_id=response_id,
            ).with_sanitized_visible_text()
            yield AIModelStreamEvent.final(
                source_id=request.source_id,
                model_name=request.model_name,
                stream_id=stream_id,
                response=final_response,
            )

        return _stream()

    async def list_models(
        self,
        *,
        api_key: str | None = None,
    ) -> list[AIModelCatalogItem]:
        resolved_api_key = api_key or self.api_key
        if not self.api_base:
            raise OpenAICompatibleProviderConfigError("api_base")
        if not resolved_api_key:
            raise OpenAICompatibleProviderConfigError("api_key")

        client = _build_openai_client(
            api_key=resolved_api_key,
            api_base=self.api_base,
            timeout_seconds=self.timeout_seconds,
            extra_config=self.extra_config,
        )
        try:
            page = await client.models.list()
        finally:
            await client.close()
        return _extract_openai_models(page)

    async def embed_texts(
        self,
        request: AIModelEmbeddingRequest,
    ) -> AIModelEmbeddingResponse:
        api_base = _coerce_str(request.extra, "api_base") or self.api_base
        api_key = _coerce_str(request.extra, "api_key") or self.api_key
        if not api_base:
            raise OpenAICompatibleProviderConfigError("api_base")
        if not api_key:
            raise OpenAICompatibleProviderConfigError("api_key")

        client = _build_openai_client(
            api_key=api_key,
            api_base=api_base,
            timeout_seconds=self.timeout_seconds,
            extra_config=self.extra_config,
        )
        try:
            payload: dict[str, Any] = {
                "model": request.model_name,
                "input": list(request.texts),
            }
            dimensions = _coerce_int(
                request.extra, "embedding_dimensions"
            ) or _coerce_int(
                self.extra_config,
                "embedding_dimensions",
            )
            if dimensions is not None and dimensions > 0:
                payload["dimensions"] = dimensions
            response = await client.embeddings.create(
                **payload,
            )
        finally:
            await client.close()
        raw = response.model_dump(mode="json")
        return AIModelEmbeddingResponse(
            source_id=request.source_id,
            model_name=request.model_name,
            vectors=tuple(_extract_openai_embeddings(response)),
            raw=raw,
            usage=raw.get("usage") if isinstance(raw.get("usage"), dict) else None,
        )

    async def transcribe_audio(
        self,
        request: AIModelTranscriptionRequest,
    ) -> AIModelTranscriptionResponse:
        api_base = _coerce_str(request.extra, "api_base") or self.api_base
        api_key = _coerce_str(request.extra, "api_key") or self.api_key
        if not api_base:
            raise OpenAICompatibleProviderConfigError("api_base")
        if not api_key:
            raise OpenAICompatibleProviderConfigError("api_key")

        payload: dict[str, Any] = {
            "file": (request.file_name, request.audio_bytes, request.mime_type),
            "model": request.model_name,
        }
        if request.language:
            payload["language"] = request.language
        client = _build_openai_client(
            api_key=api_key,
            api_base=api_base,
            timeout_seconds=self.timeout_seconds,
            extra_config=self.extra_config,
        )
        try:
            response = await client.audio.transcriptions.create(**payload)
        finally:
            await client.close()
        raw = (
            response.model_dump(mode="json")
            if hasattr(response, "model_dump")
            else None
        )
        return AIModelTranscriptionResponse(
            source_id=request.source_id,
            model_name=request.model_name,
            text=_extract_openai_transcription_text(response),
            raw=raw,
            usage=(
                raw.get("usage")
                if isinstance(raw, dict) and isinstance(raw.get("usage"), dict)
                else None
            ),
        )

    async def synthesize_speech(
        self,
        request: AIModelSpeechRequest,
    ) -> AIModelSpeechResponse:
        api_base = _coerce_str(request.extra, "api_base") or self.api_base
        api_key = _coerce_str(request.extra, "api_key") or self.api_key
        if not api_base:
            raise OpenAICompatibleProviderConfigError("api_base")
        if not api_key:
            raise OpenAICompatibleProviderConfigError("api_key")

        client = _build_openai_client(
            api_key=api_key,
            api_base=api_base,
            timeout_seconds=self.timeout_seconds,
            extra_config=self.extra_config,
        )
        try:
            response = await client.audio.speech.create(
                input=request.text,
                model=request.model_name,
                voice=request.voice,
                response_format=request.response_format,
            )
        finally:
            await client.close()
        return AIModelSpeechResponse(
            source_id=request.source_id,
            model_name=request.model_name,
            audio_bytes=response.content,
            response_format=request.response_format,
            raw=None,
        )

    async def rerank_documents(
        self,
        request: AIModelRerankRequest,
    ) -> AIModelRerankResponse:
        _ = request
        raise OpenAICompatibleProviderCapabilityError("rerank")


def _coerce_response_format(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    response_type = value.get("type")
    if response_type == "json_object":
        return {"type": "json_object"}
    if response_type != "json_schema":
        return None
    json_schema = value.get("json_schema")
    if not isinstance(json_schema, dict):
        return None
    name = json_schema.get("name")
    schema = json_schema.get("schema")
    if not isinstance(name, str) or not name.strip() or not isinstance(schema, dict):
        return None
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": name,
            "schema": schema,
        },
    }
    strict = json_schema.get("strict")
    if isinstance(strict, bool):
        response_format["json_schema"]["strict"] = strict
    return response_format


def _build_openai_chat_payload(  # noqa: PLR0913
    *,
    model_name: str,
    prompt: str,
    messages: tuple[AIModelMessage, ...],
    tools: tuple[Any, ...],
    temperature: float | None,
    max_tokens: int | None,
    options: dict[str, Any],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model_name,
        "messages": (
            _build_openai_messages(messages)
            if messages
            else [{"role": "user", "content": prompt}]
        ),
    }
    if tools:
        payload["tools"] = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in tools
        ]
    resolved_temperature = temperature
    if resolved_temperature is None:
        resolved_temperature = _coerce_float(options, "temperature")
    if resolved_temperature is not None:
        payload["temperature"] = resolved_temperature
    resolved_max_tokens = max_tokens or _coerce_int(options, "max_tokens")
    if resolved_max_tokens is not None:
        payload["max_tokens"] = resolved_max_tokens
    response_format = _coerce_response_format(
        options.get(AI_MODEL_RESPONSE_FORMAT_OPTION)
    )
    if response_format is not None:
        payload["response_format"] = response_format
    reasoning_effort = normalize_reasoning_effort(
        options.get(AI_MODEL_REASONING_EFFORT_OPTION)
    )
    if reasoning_effort is not None:
        payload["reasoning_effort"] = reasoning_effort
    return payload


def _normalize_openai_api_base(api_base: str | None) -> str | None:
    if not isinstance(api_base, str) or not api_base.strip():
        return None
    return api_base.strip().rstrip("/")


def _build_openai_client(
    *,
    api_key: str,
    api_base: str | None,
    timeout_seconds: int | None,
    extra_config: dict[str, Any],
) -> AsyncOpenAI:
    proxy = _coerce_str(extra_config, "proxy")
    http_client = httpx.AsyncClient(proxy=proxy) if proxy else None
    max_retries = _coerce_int(extra_config, "max_retries")
    return AsyncOpenAI(
        api_key=api_key,
        base_url=api_base,
        timeout=timeout_seconds,
        max_retries=max_retries if max_retries is not None else 1,
        default_headers=_coerce_custom_headers(extra_config),
        http_client=http_client,
    )


def _extract_openai_content(response: Any) -> str:
    choices = getattr(response, "choices", None)
    if not isinstance(choices, list) or not choices:
        return ""
    message = getattr(choices[0], "message", None)
    content = getattr(message, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            text = getattr(item, "text", None)
            if isinstance(text, str):
                parts.append(text)
        return "\n".join(parts)
    return ""


def _extract_openai_models(page: Any) -> list[AIModelCatalogItem]:
    rows = getattr(page, "data", None)
    if not isinstance(rows, list):
        return []
    models: list[AIModelCatalogItem] = []
    for row in rows:
        model_id = getattr(row, "id", None)
        if not isinstance(model_id, str):
            continue
        models.append(AIModelCatalogItem(id=model_id, name=model_id))
    return models


def _extract_openai_embeddings(response: Any) -> list[tuple[float, ...]]:
    rows = getattr(response, "data", None)
    if not isinstance(rows, list):
        return []
    embeddings: list[tuple[float, ...]] = []
    for row in rows:
        vector = getattr(row, "embedding", None)
        if not isinstance(vector, list):
            continue
        numeric = tuple(
            float(value) for value in vector if isinstance(value, (int, float))
        )
        if numeric:
            embeddings.append(numeric)
    return embeddings


def _extract_openai_transcription_text(response: Any) -> str:
    if isinstance(response, str):
        return response
    text = getattr(response, "text", None)
    return text if isinstance(text, str) else ""


def _extract_openai_tool_calls(response: Any) -> list[AIModelToolCall]:
    choices = getattr(response, "choices", None)
    if not isinstance(choices, list) or not choices:
        return []
    message = getattr(choices[0], "message", None)
    tool_calls = getattr(message, "tool_calls", None)
    if not isinstance(tool_calls, list):
        return []

    extracted: list[AIModelToolCall] = []
    for index, tool_call in enumerate(tool_calls):
        function = getattr(tool_call, "function", None)
        name = getattr(function, "name", None)
        if not isinstance(name, str) or not name.strip():
            continue
        arguments = _parse_tool_arguments(getattr(function, "arguments", None))
        extracted.append(
            AIModelToolCall(
                tool_call_id=str(
                    getattr(tool_call, "id", None) or f"tool_call_{index}"
                ),
                name=name,
                arguments=arguments,
            )
        )
    return extracted


def _extract_openai_finish_reason(response: Any) -> str | None:
    choices = getattr(response, "choices", None)
    if not isinstance(choices, list) or not choices:
        return None
    reason = getattr(choices[0], "finish_reason", None)
    return reason if isinstance(reason, str) else None


def _extract_openai_reasoning_content(response: Any) -> str | None:
    choices = getattr(response, "choices", None)
    if not isinstance(choices, list) or not choices:
        return None
    message = getattr(choices[0], "message", None)
    value = getattr(message, "reasoning_content", None)
    return value if isinstance(value, str) and value else None


def _extract_openai_provider_data(raw: dict[str, Any]) -> dict[str, Any] | None:
    data = {
        key: raw[key]
        for key in ("system_fingerprint", "service_tier")
        if key in raw and raw[key] is not None
    }
    return data or None


def _extract_openai_stream_response_id(chunk: Any) -> str | None:
    value = getattr(chunk, "id", None)
    return str(value) if value is not None else None


def _extract_openai_stream_delta(chunk: Any) -> str:
    choices = getattr(chunk, "choices", None)
    if not isinstance(choices, list) or not choices:
        return ""
    delta = getattr(choices[0], "delta", None)
    content = getattr(delta, "content", None)
    return content if isinstance(content, str) else ""


def _extract_openai_stream_finish_reason(chunk: Any) -> str | None:
    choices = getattr(chunk, "choices", None)
    if not isinstance(choices, list) or not choices:
        return None
    reason = getattr(choices[0], "finish_reason", None)
    return reason if isinstance(reason, str) else None


def _extract_openai_stream_usage(chunk: Any) -> dict[str, Any] | None:
    usage = getattr(chunk, "usage", None)
    if isinstance(usage, dict):
        return usage
    if usage is not None and hasattr(usage, "model_dump"):
        raw_usage = usage.model_dump(mode="json")
        return raw_usage if isinstance(raw_usage, dict) else None
    return None


def _parse_tool_arguments(arguments: Any) -> dict[str, Any]:
    if isinstance(arguments, dict):
        return arguments
    if not isinstance(arguments, str) or not arguments.strip():
        return {}
    try:
        parsed = json.loads(arguments)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _build_openai_messages(
    messages: tuple[AIModelMessage, ...],
) -> list[dict[str, Any]]:
    """Convert ``AIModelMessage`` sequence to OpenAI chat message format."""

    result: list[dict[str, Any]] = []
    for msg in messages:
        if msg.role == "system":
            result.append({"role": "system", "content": msg.text_content})
        elif msg.role == "user":
            result.append(
                {
                    "role": "user",
                    "content": (
                        _build_openai_content_parts(msg)
                        if msg.parts
                        else msg.text_content
                    ),
                }
            )
        elif msg.role == "assistant":
            entry: dict[str, Any] = {
                "role": "assistant",
                "content": msg.text_content,
            }
            if msg.tool_calls:
                entry["tool_calls"] = [
                    {
                        "id": tc.tool_call_id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                        },
                    }
                    for tc in msg.tool_calls
                ]
            result.append(entry)
        elif msg.role == "tool":
            result.append(
                {
                    "role": "tool",
                    "tool_call_id": msg.tool_call_id or "",
                    "content": msg.text_content,
                }
            )
    return result


def _build_openai_content_parts(msg: AIModelMessage) -> list[dict[str, Any]] | str:
    parts: list[dict[str, Any]] = []
    for part in msg.parts:
        if part.kind == "text" and part.text:
            parts.append({"type": "text", "text": part.text})
        elif part.kind == "image" and part.url:
            parts.append({"type": "image_url", "image_url": {"url": part.url}})
        elif part.kind == "image" and part.data:
            parts.append(
                {
                    "type": "image_url",
                    "image_url": {"url": _data_url(part.mime_type, part.data)},
                }
            )
        elif part.kind == "audio" and part.data:
            parts.append(
                {
                    "type": "input_audio",
                    "input_audio": {
                        "data": base64.b64encode(part.data).decode("ascii"),
                        "format": _openai_audio_format(part.mime_type),
                    },
                }
            )
        elif part.kind == "file" and part.data:
            parts.append(
                {
                    "type": "file",
                    "file": {
                        "filename": _metadata_str(part.metadata, "file_name")
                        or "attachment",
                        "file_data": _data_url(part.mime_type, part.data),
                    },
                }
            )
        elif part.kind == "file" and part.url:
            parts.append(
                {
                    "type": "file",
                    "file": {
                        "filename": _metadata_str(part.metadata, "file_name")
                        or "attachment",
                        "file_url": part.url,
                    },
                }
            )
        elif part.kind in {"image", "audio", "file"}:
            parts.append({"type": "text", "text": _unsupported_part_text(part.kind)})
    return parts or msg.text_content


def _data_url(mime_type: str | None, data: bytes) -> str:
    media_type = mime_type or "application/octet-stream"
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{media_type};base64,{encoded}"


def _openai_audio_format(mime_type: str | None) -> str:
    if not mime_type:
        return "wav"
    subtype = mime_type.split("/", 1)[-1].split(";", 1)[0].strip().lower()
    return subtype or "wav"


def _metadata_str(metadata: dict[str, Any] | None, key: str) -> str | None:
    if not isinstance(metadata, dict):
        return None
    value = metadata.get(key)
    return value if isinstance(value, str) and value.strip() else None


class _ThinkTagStreamFilter:
    """Incrementally suppress complete think-tag spans from visible deltas."""

    def __init__(self) -> None:
        self._buffer = ""
        self._inside_think = False

    def feed(self, delta: str) -> str:
        self._buffer += delta
        visible: list[str] = []
        while self._buffer:
            if self._inside_think:
                close_match = re.search(r"</think>", self._buffer, re.IGNORECASE)
                if close_match is None:
                    keep = min(len(self._buffer), len("</think>") - 1)
                    self._buffer = self._buffer[-keep:] if keep else ""
                    return "".join(visible)
                self._buffer = self._buffer[close_match.end() :]
                self._inside_think = False
                continue

            open_match = re.search(r"<think\b[^>]*>", self._buffer, re.IGNORECASE)
            if open_match is None:
                keep = _partial_tag_prefix_length(self._buffer, "<think")
                if keep:
                    visible.append(self._buffer[:-keep])
                    self._buffer = self._buffer[-keep:]
                else:
                    visible.append(self._buffer)
                    self._buffer = ""
                return "".join(visible)

            visible.append(self._buffer[: open_match.start()])
            self._buffer = self._buffer[open_match.end() :]
            self._inside_think = True
        return "".join(visible)


def _partial_tag_prefix_length(buffer: str, tag_prefix: str) -> int:
    lowered = buffer.lower()
    prefix = tag_prefix.lower()
    max_length = min(len(lowered), len(prefix) - 1)
    for length in range(max_length, 0, -1):
        if prefix.startswith(lowered[-length:]):
            return length
    return 0
