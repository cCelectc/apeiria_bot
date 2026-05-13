"""Gemini native source adapter."""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

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


class GeminiNativeProviderConfigError(RuntimeError):
    """Raised when required Gemini settings are missing."""

    def __init__(self, field_name: str) -> None:
        super().__init__(f"gemini-native source requires {field_name}")


class GeminiNativeProviderCapabilityError(RuntimeError):
    """Raised when Gemini native sources lack a requested operation."""

    def __init__(self, capability: str) -> None:
        super().__init__(f"gemini-native source does not support {capability}")


class GeminiNativeProvider:
    """Gemini native adapter using the public REST API."""

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
        resolved_api_base = self.api_base
        resolved_api_key = api_key or self.api_key
        if not resolved_api_base:
            raise GeminiNativeProviderConfigError("api_base")
        if not resolved_api_key:
            raise GeminiNativeProviderConfigError("api_key")

        response = await self._request_func(
            _RequestSpec(
                method="GET",
                url=_join_url(resolved_api_base, "/models"),
                headers=_build_headers(
                    resolved_api_key,
                    custom_headers=_coerce_custom_headers(self.extra_config),
                ),
                timeout_seconds=self.timeout_seconds,
                proxy=_coerce_str(self.extra_config, "proxy"),
            )
        )
        return _extract_gemini_models(response.json())

    async def generate_text(
        self,
        request: AIModelGenerateRequest,
    ) -> AIModelGenerateResponse:
        api_base = _coerce_str(request.extra, "api_base") or self.api_base
        api_key = _coerce_str(request.extra, "api_key") or self.api_key
        if not api_base:
            raise GeminiNativeProviderConfigError("api_base")
        if not api_key:
            raise GeminiNativeProviderConfigError("api_key")

        options = request.options or request.extra or {}
        payload = _build_gemini_generate_payload(
            prompt=request.prompt,
            messages=request.messages,
            tools=request.tools,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            options=options,
        )
        response = await self._request_func(
            _RequestSpec(
                method="POST",
                url=_join_url(
                    api_base,
                    f"/models/{quote(_strip_model_prefix(request.model_name), safe='')}"
                    ":generateContent",
                ),
                headers=_build_headers(
                    api_key,
                    custom_headers=(
                        _coerce_custom_headers(request.extra)
                        or _coerce_custom_headers(self.extra_config)
                    ),
                ),
                json=payload,
                timeout_seconds=self.timeout_seconds,
                proxy=_coerce_str(request.extra, "proxy")
                or _coerce_str(self.extra_config, "proxy"),
            )
        )
        raw = response.json()
        return AIModelGenerateResponse(
            source_id=request.source_id,
            model_name=request.model_name,
            content=_extract_gemini_text(raw),
            raw=raw,
            usage=raw.get("usageMetadata") if isinstance(raw, dict) else None,
            finish_reason=_extract_gemini_finish_reason(raw),
            response_id=str(raw.get("responseId")) if raw.get("responseId") else None,
            provider_data=_extract_gemini_provider_data(raw),
        ).with_sanitized_visible_text()

    def stream_text(
        self,
        request: AIModelStreamRequest,
    ) -> "AsyncIterator[AIModelStreamEvent]":
        _ = request
        raise GeminiNativeProviderCapabilityError("streaming")

    async def embed_texts(
        self,
        request: AIModelEmbeddingRequest,
    ) -> AIModelEmbeddingResponse:
        api_base = _coerce_str(request.extra, "api_base") or self.api_base
        api_key = _coerce_str(request.extra, "api_key") or self.api_key
        if not api_base:
            raise GeminiNativeProviderConfigError("api_base")
        if not api_key:
            raise GeminiNativeProviderConfigError("api_key")

        vectors: list[tuple[float, ...]] = []
        raw_items: list[dict[str, Any]] = []
        model_path = quote(_strip_model_prefix(request.model_name), safe="")
        for text in request.texts:
            response = await self._request_func(
                _RequestSpec(
                    method="POST",
                    url=_join_url(
                        api_base,
                        f"/models/{model_path}:embedContent",
                    ),
                    headers=_build_headers(
                        api_key,
                        custom_headers=(
                            _coerce_custom_headers(request.extra)
                            or _coerce_custom_headers(self.extra_config)
                        ),
                    ),
                    json={"content": {"parts": [{"text": text}]}},
                    timeout_seconds=self.timeout_seconds,
                    proxy=_coerce_str(request.extra, "proxy")
                    or _coerce_str(self.extra_config, "proxy"),
                )
            )
            raw = response.json()
            raw_items.append(raw)
            vector = _extract_gemini_embedding(raw)
            if vector:
                vectors.append(vector)

        return AIModelEmbeddingResponse(
            source_id=request.source_id,
            model_name=request.model_name,
            vectors=tuple(vectors),
            raw={"items": raw_items},
        )

    async def transcribe_audio(
        self,
        request: AIModelTranscriptionRequest,
    ) -> AIModelTranscriptionResponse:
        _ = request
        raise GeminiNativeProviderCapabilityError("speech_to_text")

    async def synthesize_speech(
        self,
        request: AIModelSpeechRequest,
    ) -> AIModelSpeechResponse:
        _ = request
        raise GeminiNativeProviderCapabilityError("text_to_speech")

    async def rerank_documents(
        self,
        request: AIModelRerankRequest,
    ) -> AIModelRerankResponse:
        _ = request
        raise GeminiNativeProviderCapabilityError("rerank")


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


def _normalize_api_base(api_base: str | None) -> str | None:
    if not isinstance(api_base, str) or not api_base.strip():
        return None
    return api_base.strip().rstrip("/")


def _join_url(api_base: str, path: str) -> str:
    return f"{api_base.rstrip('/')}/{path.lstrip('/')}"


def _strip_model_prefix(model_name: str) -> str:
    normalized = model_name.strip()
    return normalized.removeprefix("models/")


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
    api_key: str,
    *,
    custom_headers: dict[str, str] | None = None,
) -> dict[str, str]:
    return {
        "x-goog-api-key": api_key,
        **(custom_headers or {}),
    }


def _build_gemini_generate_payload(  # noqa: PLR0913
    *,
    prompt: str,
    messages: tuple[AIModelMessage, ...],
    tools: tuple[Any, ...] = (),
    temperature: float | None,
    max_tokens: int | None,
    options: dict[str, Any],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "contents": _build_gemini_contents(messages, prompt),
    }
    generation_config: dict[str, Any] = {}
    resolved_temperature = temperature
    if resolved_temperature is None:
        resolved_temperature = _coerce_float(options, "temperature")
    if resolved_temperature is not None:
        generation_config["temperature"] = resolved_temperature
    resolved_max_tokens = max_tokens or _coerce_int(options, "max_tokens")
    if resolved_max_tokens is not None:
        generation_config["maxOutputTokens"] = resolved_max_tokens
    if generation_config:
        payload["generationConfig"] = generation_config
    system_text = "\n".join(
        message.text_content for message in messages if message.role == "system"
    ).strip()
    if system_text:
        payload["systemInstruction"] = {"parts": [{"text": system_text}]}
    if tools:
        payload["tools"] = [
            {
                "functionDeclarations": [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    }
                    for tool in tools
                ]
            }
        ]
    return payload


def _build_gemini_contents(
    messages: tuple[AIModelMessage, ...],
    prompt: str,
) -> list[dict[str, Any]]:
    if not messages:
        return [{"role": "user", "parts": [{"text": prompt}]}]
    contents: list[dict[str, Any]] = []
    for message in messages:
        if message.role == "system":
            continue
        text = message.text_content
        if not text:
            continue
        role = "model" if message.role == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": text}]})
    return contents or [{"role": "user", "parts": [{"text": prompt}]}]


def _extract_gemini_text(payload: Any) -> str:
    candidates = payload.get("candidates") if isinstance(payload, dict) else None
    if not isinstance(candidates, list) or not candidates:
        return ""
    content = candidates[0].get("content") if isinstance(candidates[0], dict) else None
    parts = content.get("parts") if isinstance(content, dict) else None
    if not isinstance(parts, list):
        return ""
    text_parts: list[str] = []
    for part in parts:
        text = part.get("text") if isinstance(part, dict) else None
        if isinstance(text, str):
            text_parts.append(text)
    return "\n".join(text_parts)


def _extract_gemini_finish_reason(payload: Any) -> str | None:
    candidates = payload.get("candidates") if isinstance(payload, dict) else None
    if not isinstance(candidates, list) or not candidates:
        return None
    reason = (
        candidates[0].get("finishReason") if isinstance(candidates[0], dict) else None
    )
    return reason if isinstance(reason, str) else None


def _extract_gemini_provider_data(payload: dict[str, Any]) -> dict[str, Any] | None:
    data = {
        key: payload[key]
        for key in ("modelVersion",)
        if key in payload and payload[key] is not None
    }
    return data or None


def _extract_gemini_embedding(payload: Any) -> tuple[float, ...]:
    embedding = payload.get("embedding") if isinstance(payload, dict) else None
    values = embedding.get("values") if isinstance(embedding, dict) else None
    if not isinstance(values, list):
        return ()
    return tuple(float(value) for value in values if isinstance(value, (int, float)))


def _extract_gemini_models(payload: Any) -> list[AIModelCatalogItem]:
    rows = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return []
    models: list[AIModelCatalogItem] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        raw_name = row.get("name")
        if not isinstance(raw_name, str) or not raw_name.strip():
            continue
        model_id = _strip_model_prefix(raw_name)
        display_name = row.get("displayName")
        models.append(
            AIModelCatalogItem(
                id=model_id,
                name=display_name if isinstance(display_name, str) else model_id,
            )
        )
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
