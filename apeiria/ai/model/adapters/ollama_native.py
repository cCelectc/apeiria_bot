"""Ollama native source adapter."""

from __future__ import annotations

import base64
from http import HTTPStatus
from typing import TYPE_CHECKING, Any

import httpx

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
    AIModelStreamRequest,
    AIModelTranscriptionRequest,
    AIModelTranscriptionResponse,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from apeiria.ai.model.runtime.adapter import AIModelStreamEvent


_DEFAULT_TIMEOUT_SECONDS = 20


class OllamaNativeProviderConfigError(RuntimeError):
    """Raised when required Ollama settings are missing."""

    def __init__(self, field_name: str) -> None:
        super().__init__(f"ollama-native source requires {field_name}")


class OllamaNativeProviderCapabilityError(RuntimeError):
    """Raised when Ollama native sources lack a requested operation."""

    def __init__(self, capability: str) -> None:
        super().__init__(f"ollama-native source does not support {capability}")


class OllamaNativeProvider:
    """Ollama native adapter using the local HTTP API."""

    def __init__(
        self,
        *,
        api_base: str | None,
        api_key: str | None = None,
        timeout_seconds: int | None = None,
        extra_config: dict[str, Any] | None = None,
        request_func: Any | None = None,
    ) -> None:
        self.api_base = _normalize_api_base(api_base)
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.extra_config = extra_config or {}
        self._request_func = request_func or _request_json

    async def list_models(
        self,
        *,
        api_key: str | None = None,
    ) -> list[AIModelCatalogItem]:
        _ = api_key
        if not self.api_base:
            raise OllamaNativeProviderConfigError("api_base")

        response = await self._request_func(
            _RequestSpec(
                method="GET",
                url=_join_url(self.api_base, "/api/tags"),
                headers=_build_headers(
                    self.api_key,
                    custom_headers=_coerce_custom_headers(self.extra_config),
                ),
                timeout_seconds=self.timeout_seconds,
                proxy=_coerce_str(self.extra_config, "proxy"),
            )
        )
        return _extract_ollama_models(response.json())

    async def generate_text(
        self,
        request: AIModelGenerateRequest,
    ) -> AIModelGenerateResponse:
        api_base = _coerce_str(request.extra, "api_base") or self.api_base
        if not api_base:
            raise OllamaNativeProviderConfigError("api_base")

        options = request.options or request.extra or {}
        response = await self._request_func(
            _RequestSpec(
                method="POST",
                url=_join_url(api_base, "/api/chat"),
                headers=_build_headers(
                    _coerce_str(request.extra, "api_key") or self.api_key,
                    custom_headers=(
                        _coerce_custom_headers(request.extra)
                        or _coerce_custom_headers(self.extra_config)
                    ),
                ),
                json=_build_ollama_chat_payload(
                    _ChatPayloadInput(
                        model_name=request.model_name,
                        prompt=request.prompt,
                        messages=request.messages,
                        temperature=request.temperature,
                        max_tokens=request.max_tokens,
                        options=options,
                    )
                ),
                timeout_seconds=self.timeout_seconds,
                proxy=_coerce_str(request.extra, "proxy")
                or _coerce_str(self.extra_config, "proxy"),
            )
        )
        raw = response.json()
        return AIModelGenerateResponse(
            source_id=request.source_id,
            model_name=request.model_name,
            content=_extract_ollama_text(raw),
            raw=raw,
            usage=_extract_ollama_usage(raw),
            finish_reason=_extract_ollama_finish_reason(raw),
        ).with_sanitized_visible_text()

    def stream_text(
        self,
        request: AIModelStreamRequest,
    ) -> "AsyncIterator[AIModelStreamEvent]":
        _ = request
        raise OllamaNativeProviderCapabilityError("streaming")

    async def embed_texts(
        self,
        request: AIModelEmbeddingRequest,
    ) -> AIModelEmbeddingResponse:
        api_base = _coerce_str(request.extra, "api_base") or self.api_base
        if not api_base:
            raise OllamaNativeProviderConfigError("api_base")

        response = await self._request_func(
            _RequestSpec(
                method="POST",
                url=_join_url(api_base, "/api/embed"),
                headers=_build_headers(
                    _coerce_str(request.extra, "api_key") or self.api_key,
                    custom_headers=(
                        _coerce_custom_headers(request.extra)
                        or _coerce_custom_headers(self.extra_config)
                    ),
                ),
                json={
                    "model": request.model_name,
                    "input": list(request.texts),
                },
                timeout_seconds=self.timeout_seconds,
                proxy=_coerce_str(request.extra, "proxy")
                or _coerce_str(self.extra_config, "proxy"),
            )
        )
        raw = response.json()
        return AIModelEmbeddingResponse(
            source_id=request.source_id,
            model_name=request.model_name,
            vectors=tuple(_extract_ollama_embeddings(raw)),
            raw=raw if isinstance(raw, dict) else None,
            usage=_extract_ollama_usage(raw),
        )

    async def transcribe_audio(
        self,
        request: AIModelTranscriptionRequest,
    ) -> AIModelTranscriptionResponse:
        _ = request
        raise OllamaNativeProviderCapabilityError("speech_to_text")

    async def synthesize_speech(
        self,
        request: AIModelSpeechRequest,
    ) -> AIModelSpeechResponse:
        _ = request
        raise OllamaNativeProviderCapabilityError("text_to_speech")

    async def rerank_documents(
        self,
        request: AIModelRerankRequest,
    ) -> AIModelRerankResponse:
        _ = request
        raise OllamaNativeProviderCapabilityError("rerank")


class _RequestSpec:
    def __init__(  # noqa: PLR0913
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
        timeout_seconds: int | None = None,
        proxy: str | None = None,
    ) -> None:
        self.method = method
        self.url = url
        self.headers = headers
        self.json = json
        self.timeout_seconds = timeout_seconds
        self.proxy = proxy


class _ChatPayloadInput:
    def __init__(  # noqa: PLR0913
        self,
        *,
        model_name: str,
        prompt: str,
        messages: tuple[AIModelMessage, ...],
        temperature: float | None,
        max_tokens: int | None,
        options: dict[str, Any],
    ) -> None:
        self.model_name = model_name
        self.prompt = prompt
        self.messages = messages
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.options = options


def _normalize_api_base(api_base: str | None) -> str | None:
    if not isinstance(api_base, str) or not api_base.strip():
        return None
    return api_base.strip().rstrip("/")


def _join_url(api_base: str, path: str) -> str:
    return f"{api_base.rstrip('/')}/{path.lstrip('/')}"


def _coerce_str(extra: dict[str, Any] | None, key: str) -> str | None:
    if not extra:
        return None
    value = extra.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else None


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


def _coerce_float(extra: dict[str, Any] | None, key: str) -> float | None:
    if not extra:
        return None
    value = extra.get(key)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _coerce_custom_headers(extra: dict[str, Any] | None) -> dict[str, str] | None:
    if not extra:
        return None
    raw = extra.get("_custom_headers")
    if not isinstance(raw, dict):
        return None
    headers = {
        key.strip(): value.strip()
        for key, value in raw.items()
        if isinstance(key, str)
        and key.strip()
        and isinstance(value, str)
        and value.strip()
    }
    return headers or None


def _build_headers(
    api_key: str | None,
    *,
    custom_headers: dict[str, str] | None = None,
) -> dict[str, str] | None:
    headers = dict(custom_headers or {})
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers or None


def _build_ollama_chat_payload(payload_input: _ChatPayloadInput) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": payload_input.model_name,
        "messages": (
            _build_ollama_messages(payload_input.messages)
            if payload_input.messages
            else [{"role": "user", "content": payload_input.prompt}]
        ),
        "stream": False,
    }
    provider_options: dict[str, Any] = {}
    resolved_temperature = payload_input.temperature
    if resolved_temperature is None:
        resolved_temperature = _coerce_float(payload_input.options, "temperature")
    if resolved_temperature is not None:
        provider_options["temperature"] = resolved_temperature
    resolved_max_tokens = payload_input.max_tokens or _coerce_int(
        payload_input.options,
        "max_tokens",
    )
    if resolved_max_tokens is not None:
        provider_options["num_predict"] = resolved_max_tokens
    if provider_options:
        payload["options"] = provider_options
    return payload


def _build_ollama_messages(
    messages: tuple[AIModelMessage, ...],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for message in messages:
        text = _ollama_message_text(message)
        images = _ollama_message_images(message)
        if not text and not images:
            continue
        role = message.role
        if role == "tool":
            role = "user"
        item: dict[str, Any] = {"role": role, "content": text}
        if images:
            item["images"] = images
        items.append(item)
    return items


def _ollama_message_text(message: AIModelMessage) -> str:
    text_items: list[str] = []
    if message.text_content:
        text_items.append(message.text_content)
    for part in getattr(message, "parts", ()):
        kind = getattr(part, "kind", None)
        if kind == "image" and not getattr(part, "data", None):
            text_items.append(_unsupported_part_text("image"))
        elif kind in {"audio", "file"}:
            text_items.append(_unsupported_part_text(str(kind)))
    return "\n".join(dict.fromkeys(item for item in text_items if item))


def _ollama_message_images(message: AIModelMessage) -> list[str]:
    images: list[str] = []
    for part in getattr(message, "parts", ()):
        if getattr(part, "kind", None) != "image":
            continue
        data = getattr(part, "data", None)
        if isinstance(data, bytes) and data:
            images.append(base64.b64encode(data).decode("ascii"))
    return images


def _unsupported_part_text(kind: str) -> str:
    return f"[{kind} omitted: unsupported content representation]"


def _extract_ollama_text(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    message = payload.get("message")
    if isinstance(message, dict) and isinstance(message.get("content"), str):
        return message["content"]
    response = payload.get("response")
    return response if isinstance(response, str) else ""


def _extract_ollama_finish_reason(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    reason = payload.get("done_reason")
    return reason if isinstance(reason, str) else None


def _extract_ollama_usage(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    usage = {
        key: payload[key]
        for key in (
            "prompt_eval_count",
            "eval_count",
            "total_duration",
            "load_duration",
            "prompt_eval_duration",
            "eval_duration",
        )
        if key in payload and payload[key] is not None
    }
    return usage or None


def _extract_ollama_embeddings(payload: Any) -> list[tuple[float, ...]]:
    rows = payload.get("embeddings") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        embedding = payload.get("embedding") if isinstance(payload, dict) else None
        rows = [embedding] if isinstance(embedding, list) else []
    vectors: list[tuple[float, ...]] = []
    for row in rows:
        if not isinstance(row, list):
            continue
        vector = tuple(float(value) for value in row if isinstance(value, (int, float)))
        if vector:
            vectors.append(vector)
    return vectors


def _extract_ollama_models(payload: Any) -> list[AIModelCatalogItem]:
    rows = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return []
    models: list[AIModelCatalogItem] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = row.get("model") or row.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        models.append(AIModelCatalogItem(id=name, name=name))
    return models


async def _request_json(spec: _RequestSpec) -> httpx.Response:
    async with httpx.AsyncClient(
        timeout=float(spec.timeout_seconds or _DEFAULT_TIMEOUT_SECONDS),
        proxy=spec.proxy,
    ) as client:
        response = await client.request(
            spec.method,
            spec.url,
            headers=spec.headers,
            json=spec.json,
        )
    if response.status_code >= HTTPStatus.BAD_REQUEST:
        response.raise_for_status()
    return response
