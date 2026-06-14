"""Generic rerank API source adapter."""

from __future__ import annotations

import asyncio
from http import HTTPStatus
from typing import TYPE_CHECKING, Any

import httpx
from nonebot.log import logger

from apeiria.ai.model.adapters._common import (
    _coerce_custom_headers,
    _coerce_float,
    _coerce_int,
    _coerce_str,
)
from apeiria.ai.model.runtime.adapter import (
    AIModelCatalogItem,
    AIModelEmbeddingRequest,
    AIModelEmbeddingResponse,
    AIModelGenerateRequest,
    AIModelGenerateResponse,
    AIModelRerankRequest,
    AIModelRerankResponse,
    AIModelRerankResultItem,
    AIModelSpeechRequest,
    AIModelSpeechResponse,
    AIModelStreamRequest,
    AIModelTranscriptionRequest,
    AIModelTranscriptionResponse,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from apeiria.ai.model.runtime.adapter import AIModelStreamEvent


class GenericRerankProviderConfigError(RuntimeError):
    """Raised when required generic rerank settings are missing."""

    def __init__(self, field_name: str) -> None:
        super().__init__(f"generic rerank source requires {field_name}")


class GenericRerankProviderCapabilityError(RuntimeError):
    """Raised when a capability is unsupported by the generic rerank adapter."""

    def __init__(self, capability: str) -> None:
        super().__init__(f"generic rerank source does not support {capability}")


class GenericRerankProvider:
    """Generic adapter for common `/rerank` style APIs."""

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
        self._request_func = request_func

    async def list_models(
        self,
        *,
        api_key: str | None = None,
    ) -> list[AIModelCatalogItem]:
        resolved_api_key = api_key or self.api_key
        if not self.api_base:
            raise GenericRerankProviderConfigError("api_base")
        if not resolved_api_key:
            raise GenericRerankProviderConfigError("api_key")

        async with httpx.AsyncClient(
            base_url=self.api_base,
            headers=_build_headers(
                resolved_api_key,
                custom_headers=_coerce_custom_headers(self.extra_config),
            ),
            timeout=float(self.timeout_seconds or 20),
            proxy=_coerce_str(self.extra_config, "proxy"),
        ) as client:
            response = await _request_with_retries(
                client.get,
                "/models",
                max_retries=_coerce_int(self.extra_config, "max_retries") or 1,
                backoff_seconds=(
                    _coerce_float(self.extra_config, "retry_backoff_seconds") or 0.25
                ),
            )
            if response.status_code >= HTTPStatus.BAD_REQUEST:
                return []
            payload = response.json()
        return _extract_openai_like_models(payload)

    async def generate_text(
        self,
        request: AIModelGenerateRequest,
    ) -> AIModelGenerateResponse:
        _ = request
        raise GenericRerankProviderCapabilityError("chat_completion")

    def stream_text(
        self,
        request: AIModelStreamRequest,
    ) -> "AsyncIterator[AIModelStreamEvent]":
        _ = request
        raise GenericRerankProviderCapabilityError("streaming")

    async def embed_texts(
        self,
        request: AIModelEmbeddingRequest,
    ) -> AIModelEmbeddingResponse:
        _ = request
        raise GenericRerankProviderCapabilityError("embedding")

    async def transcribe_audio(
        self,
        request: AIModelTranscriptionRequest,
    ) -> AIModelTranscriptionResponse:
        _ = request
        raise GenericRerankProviderCapabilityError("speech_to_text")

    async def synthesize_speech(
        self,
        request: AIModelSpeechRequest,
    ) -> AIModelSpeechResponse:
        _ = request
        raise GenericRerankProviderCapabilityError("text_to_speech")

    async def rerank_documents(
        self,
        request: AIModelRerankRequest,
    ) -> AIModelRerankResponse:
        api_key = _coerce_str(request.extra, "api_key") or self.api_key
        if not self.api_base:
            raise GenericRerankProviderConfigError("api_base")
        if not api_key:
            raise GenericRerankProviderConfigError("api_key")

        payload = {
            "model": request.model_name,
            "query": request.query,
            "documents": list(request.documents),
            "top_n": request.top_n,
        }
        api_suffix = (
            _coerce_str(request.extra, "api_suffix")
            or _coerce_str(
                self.extra_config,
                "api_suffix",
            )
            or "/rerank"
        )
        request_func = self._request_func
        if request_func is None:
            async with httpx.AsyncClient(
                base_url=self.api_base,
                headers=_build_headers(
                    api_key,
                    custom_headers=(
                        _coerce_custom_headers(request.extra)
                        or _coerce_custom_headers(self.extra_config)
                    ),
                ),
                timeout=float(self.timeout_seconds or 20),
                proxy=_coerce_str(request.extra, "proxy")
                or _coerce_str(self.extra_config, "proxy"),
            ) as client:
                response = await _request_with_retries(
                    client.post,
                    _normalize_api_suffix(api_suffix),
                    json=payload,
                    max_retries=(
                        _coerce_int(request.extra, "max_retries")
                        or _coerce_int(self.extra_config, "max_retries")
                        or 1
                    ),
                    backoff_seconds=(
                        _coerce_float(request.extra, "retry_backoff_seconds")
                        or _coerce_float(self.extra_config, "retry_backoff_seconds")
                        or 0.25
                    ),
                )
        else:
            response = await request_func(
                _normalize_api_suffix(api_suffix),
                json=payload,
            )
        response.raise_for_status()
        raw = response.json()
        raw_payload = raw if isinstance(raw, dict) else None
        return AIModelRerankResponse(
            source_id=request.source_id,
            model_name=request.model_name,
            results=tuple(_extract_rerank_results(raw, request.documents)),
            raw=raw_payload,
            usage=(
                raw_payload.get("usage")
                if raw_payload is not None
                and isinstance(raw_payload.get("usage"), dict)
                else None
            ),
        )


def _normalize_api_base(api_base: str | None) -> str | None:
    if not isinstance(api_base, str) or not api_base.strip():
        return None
    return api_base.strip().rstrip("/")


def _normalize_api_suffix(api_suffix: str) -> str:
    normalized = api_suffix.strip() or "/rerank"
    return normalized if normalized.startswith("/") else f"/{normalized}"


def _build_headers(
    api_key: str,
    *,
    custom_headers: dict[str, str] | None = None,
) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        **(custom_headers or {}),
    }


async def _request_with_retries(
    request_func: Any,
    *args: object,
    max_retries: int,
    backoff_seconds: float,
    **kwargs: object,
) -> httpx.Response:
    attempts = max(max_retries, 0) + 1
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = await request_func(*args, **kwargs)
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            last_error = exc
            if attempt >= attempts:
                raise
            logger.warning(
                "generic rerank request failed attempt={}/{} error={}",
                attempt,
                attempts,
                exc,
            )
            await asyncio.sleep(backoff_seconds * attempt)
            continue

        if (
            response.status_code >= HTTPStatus.INTERNAL_SERVER_ERROR
            and attempt < attempts
        ):
            logger.warning(
                "generic rerank upstream 5xx attempt={}/{} status={}",
                attempt,
                attempts,
                response.status_code,
            )
            await asyncio.sleep(backoff_seconds * attempt)
            continue
        return response

    assert last_error is not None
    raise last_error


def _extract_openai_like_models(payload: Any) -> list[AIModelCatalogItem]:
    rows = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return []
    items: list[AIModelCatalogItem] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        model_id = row.get("id")
        if not isinstance(model_id, str) or not model_id.strip():
            continue
        items.append(AIModelCatalogItem(id=model_id, name=model_id))
    return items


def _extract_rerank_results(
    payload: Any,
    documents: tuple[str, ...],
) -> list[AIModelRerankResultItem]:
    rows = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return []
    results: list[AIModelRerankResultItem] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        index = row.get("index")
        score = row.get("relevance_score", row.get("score"))
        if not isinstance(index, int) or not isinstance(score, (int, float)):
            continue
        document = documents[index] if 0 <= index < len(documents) else None
        results.append(
            AIModelRerankResultItem(
                index=index,
                relevance_score=float(score),
                document=document,
            )
        )
    return results
