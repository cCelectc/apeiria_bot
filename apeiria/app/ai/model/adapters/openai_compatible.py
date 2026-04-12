"""OpenAI-compatible source adapter."""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit
from typing import TYPE_CHECKING, Any

from apeiria.app.ai.model.adapter import (
    AIModelCatalogItem,
    AIModelGenerateRequest,
    AIModelGenerateResponse,
    AIModelToolCall,
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
        super().__init__(f"openai-compatible source requires {field_name}")


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
        self.api_base = _normalize_openai_api_base(api_base)
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

        raw = await self._request_func(
            f"{api_base.rstrip('/')}/chat/completions",
            {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            payload,
        )
        return AIModelGenerateResponse(
            source_id=request.source_id,
            model_name=request.model_name,
            content=_extract_openai_content(raw),
            tool_calls=tuple(_extract_openai_tool_calls(raw)),
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


def _normalize_openai_api_base(api_base: str | None) -> str | None:
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


def _extract_openai_models(raw: dict[str, Any]) -> list[AIModelCatalogItem]:
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
        models.append(AIModelCatalogItem(id=model_id, name=model_id))
    return models


def _extract_openai_tool_calls(raw: dict[str, Any]) -> list[AIModelToolCall]:
    choices = raw.get("choices")
    if not isinstance(choices, list) or not choices:
        return []
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        return []
    message = first_choice.get("message")
    if not isinstance(message, dict):
        return []
    tool_calls = message.get("tool_calls")
    if not isinstance(tool_calls, list):
        return []

    extracted: list[AIModelToolCall] = []
    for index, tool_call in enumerate(tool_calls):
        if not isinstance(tool_call, dict):
            continue
        function = tool_call.get("function")
        if not isinstance(function, dict):
            continue
        name = function.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        arguments = _parse_tool_arguments(function.get("arguments"))
        extracted.append(
            AIModelToolCall(
                tool_call_id=str(tool_call.get("id") or f"tool_call_{index}"),
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
    import json

    try:
        parsed = json.loads(arguments)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
