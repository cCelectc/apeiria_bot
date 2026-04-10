"""OpenAI-compatible provider adapter."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from apeiria.app.ai.model.provider import (
    AIModelGenerateRequest,
    AIModelGenerateResponse,
    AIProviderModelItem,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    OpenAIRequestFunc = Callable[
        [str, dict[str, str], dict[str, Any]],
        Awaitable[dict[str, Any]],
    ]
    OpenAIListRequestFunc = Callable[
        [str, dict[str, str]],
        Awaitable[dict[str, Any]],
    ]


class OpenAICompatibleProviderConfigError(RuntimeError):
    """Raised when required OpenAI-compatible settings are missing."""

    def __init__(self, field_name: str) -> None:
        super().__init__(f"openai-compatible provider requires {field_name}")


class OpenAICompatibleProvider:
    """Minimal OpenAI-compatible text generation adapter."""

    def __init__(
        self,
        *,
        api_base: str | None,
        api_key: str | None = None,
        request_func: "OpenAIRequestFunc | None" = None,
        list_request_func: "OpenAIListRequestFunc | None" = None,
    ) -> None:
        self.api_base = api_base
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
            raise OpenAICompatibleProviderConfigError("api_base")
        if not api_key:
            raise OpenAICompatibleProviderConfigError("api_key")

        payload: dict[str, Any] = {
            "model": request.model_name,
            "messages": [{"role": "user", "content": request.prompt}],
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens

        raw = await self._request_func(
            f"{api_base.rstrip('/')}/chat/completions",
            {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            payload,
        )
        return AIModelGenerateResponse(
            provider_id=request.provider_id,
            model_name=request.model_name,
            content=_extract_openai_content(raw),
            raw=raw,
        )

    async def list_models(
        self,
        *,
        api_key: str | None = None,
    ) -> list[AIProviderModelItem]:
        resolved_api_key = api_key or self.api_key
        if not self.api_base:
            raise OpenAICompatibleProviderConfigError("api_base")
        if not resolved_api_key:
            raise OpenAICompatibleProviderConfigError("api_key")

        raw = await self._list_request_func(
            f"{self.api_base.rstrip('/')}/models",
            {
                "Authorization": f"Bearer {resolved_api_key}",
                "Content-Type": "application/json",
            },
        )
        return _extract_openai_models(raw)

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
            return await response.json()

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
            return await response.json()


def _coerce_str(extra: dict[str, Any] | None, key: str) -> str | None:
    if not extra:
        return None
    value = extra.get(key)
    return value if isinstance(value, str) and value.strip() else None


def _wrap_list_request(
    request_func: "OpenAIRequestFunc | None",
) -> "OpenAIListRequestFunc | None":
    if request_func is None:
        return None

    async def _wrapped(
        url: str,
        headers: dict[str, str],
    ) -> dict[str, Any]:
        return await request_func(url, headers, {})

    return _wrapped


def _extract_openai_content(raw: dict[str, Any]) -> str:
    choices = raw.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        return ""
    message = first_choice.get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    return content if isinstance(content, str) else ""


def _extract_openai_models(raw: dict[str, Any]) -> list[AIProviderModelItem]:
    rows = raw.get("data")
    if not isinstance(rows, list):
        return []
    models: list[AIProviderModelItem] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        model_id = row.get("id")
        if not isinstance(model_id, str):
            continue
        models.append(AIProviderModelItem(id=model_id, name=model_id))
    return models
