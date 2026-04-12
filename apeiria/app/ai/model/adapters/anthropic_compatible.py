"""Anthropic-compatible source adapter."""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit
from typing import TYPE_CHECKING, Any

from apeiria.app.ai.model.adapter import (
    AIModelCatalogItem,
    AIModelGenerateRequest,
    AIModelGenerateResponse,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    AnthropicRequestFunc = Callable[
        [str, dict[str, str], dict[str, Any]],
        Awaitable[dict[str, Any]],
    ]
    AnthropicListRequestFunc = Callable[
        [str, dict[str, str]],
        Awaitable[dict[str, Any]],
    ]


class AnthropicCompatibleProviderConfigError(RuntimeError):
    """Raised when required Anthropic-compatible settings are missing."""

    def __init__(self, field_name: str) -> None:
        super().__init__(f"anthropic-compatible source requires {field_name}")


class AnthropicCompatibleProvider:
    """Minimal Anthropic-compatible text generation adapter."""

    def __init__(
        self,
        *,
        api_base: str | None,
        api_key: str | None = None,
        request_func: "AnthropicRequestFunc | None" = None,
        list_request_func: "AnthropicListRequestFunc | None" = None,
    ) -> None:
        self.api_base = _normalize_anthropic_api_base(api_base)
        self.api_key = api_key
        self._request_func = request_func or self._request_json
        self._list_request_func = (
            list_request_func
            or _wrap_list_request(request_func)
            or self._request_json_get
        )

    async def generate_text(
        self,
        request: AIModelGenerateRequest,
    ) -> AIModelGenerateResponse:
        api_base = _coerce_str(request.extra, "api_base") or self.api_base
        api_key = _coerce_str(request.extra, "api_key") or self.api_key
        if not api_base:
            raise AnthropicCompatibleProviderConfigError("api_base")
        if not api_key:
            raise AnthropicCompatibleProviderConfigError("api_key")

        payload: dict[str, Any] = {
            "model": request.model_name,
            "messages": [{"role": "user", "content": request.prompt}],
            "max_tokens": request.max_tokens or 1024,
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature

        raw = await self._request_func(
            f"{api_base.rstrip('/')}/messages",
            {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            payload,
        )
        return AIModelGenerateResponse(
            source_id=request.source_id,
            model_name=request.model_name,
            content=_extract_anthropic_content(raw),
            raw=raw,
        )

    async def list_models(
        self,
        *,
        api_key: str | None = None,
    ) -> list[AIModelCatalogItem]:
        resolved_api_key = api_key or self.api_key
        if not self.api_base:
            raise AnthropicCompatibleProviderConfigError("api_base")
        if not resolved_api_key:
            raise AnthropicCompatibleProviderConfigError("api_key")

        raw = await self._list_request_func(
            f"{self.api_base.rstrip('/')}/models",
            {
                "x-api-key": resolved_api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
        )
        return _extract_anthropic_models(raw)

    async def _request_json(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        import aiohttp

        async with (
            aiohttp.ClientSession(headers=headers) as session,
            session.post(url, json=payload) as response,
        ):
            response.raise_for_status()
            return await _decode_json_response(response)

    async def _request_json_get(
        self,
        url: str,
        headers: dict[str, str],
    ) -> dict[str, Any]:
        import aiohttp

        async with (
            aiohttp.ClientSession(headers=headers) as session,
            session.get(url) as response,
        ):
            response.raise_for_status()
            return await _decode_json_response(response)


def _coerce_str(extra: dict[str, Any] | None, key: str) -> str | None:
    if not extra:
        return None
    value = extra.get(key)
    return value if isinstance(value, str) and value.strip() else None


def _normalize_anthropic_api_base(api_base: str | None) -> str | None:
    if not isinstance(api_base, str) or not api_base.strip():
        return None
    normalized = api_base.strip().rstrip("/")
    parsed = urlsplit(normalized)
    if parsed.path in {"", "/"}:
        return urlunsplit((parsed.scheme, parsed.netloc, "/v1", parsed.query, parsed.fragment))
    return normalized


async def _decode_json_response(response: Any) -> dict[str, Any]:
    content_type = str(response.headers.get("Content-Type") or "").lower()
    if "json" not in content_type:
        preview = (await response.text())[:160].strip()
        msg = "模型接口返回了非 JSON 响应，请检查接口地址或接入方式。"
        if preview:
            msg = f"{msg} 响应片段: {preview}"
        raise RuntimeError(msg)
    return await response.json()


def _wrap_list_request(
    request_func: "AnthropicRequestFunc | None",
) -> "AnthropicListRequestFunc | None":
    if request_func is None:
        return None

    async def _wrapped(
        url: str,
        headers: dict[str, str],
    ) -> dict[str, Any]:
        return await request_func(url, headers, {})

    return _wrapped


def _extract_anthropic_content(raw: dict[str, Any]) -> str:
    content = raw.get("content")
    if not isinstance(content, list):
        return ""
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text":
            text = block.get("text")
            if isinstance(text, str):
                return text
    return ""


def _extract_anthropic_models(raw: dict[str, Any]) -> list[AIModelCatalogItem]:
    rows = raw.get("data")
    if not isinstance(rows, list):
        return []
    models: list[AIModelCatalogItem] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        model_id = row.get("id")
        if not isinstance(model_id, str):
            continue
        display_name = row.get("display_name")
        models.append(
            AIModelCatalogItem(
                id=model_id,
                name=display_name if isinstance(display_name, str) else model_id,
            )
        )
    return models
