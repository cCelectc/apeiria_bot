"""OpenAI-compatible source adapter."""

from __future__ import annotations

import json
from typing import Any

import httpx
from openai import AsyncOpenAI

from apeiria.app.ai.model.adapter import (
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
    AIModelToolCall,
    AIModelTranscriptionRequest,
    AIModelTranscriptionResponse,
)


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

        payload: dict[str, Any] = {
            "model": request.model_name,
            "messages": (
                _build_openai_messages(request.messages)
                if request.messages
                else [{"role": "user", "content": request.prompt}]
            ),
        }
        if request.tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                }
                for tool in request.tools
            ]
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens

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
        )

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


def _coerce_str(extra: dict[str, Any] | None, key: str) -> str | None:
    if not extra:
        return None
    value = extra.get(key)
    return value if isinstance(value, str) and value.strip() else None


def _coerce_int(extra: dict[str, Any] | None, key: str) -> int | None:
    if not extra:
        return None
    value = extra.get(key)
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None


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
    return AsyncOpenAI(
        api_key=api_key,
        base_url=api_base,
        timeout=timeout_seconds,
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
            result.append({"role": "system", "content": msg.content})
        elif msg.role == "user":
            result.append({"role": "user", "content": msg.content})
        elif msg.role == "assistant":
            entry: dict[str, Any] = {"role": "assistant", "content": msg.content}
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
                    "content": msg.content,
                }
            )
    return result
