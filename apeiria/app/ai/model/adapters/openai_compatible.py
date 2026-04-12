"""OpenAI-compatible source adapter."""

from __future__ import annotations

import json
from typing import Any

from openai import AsyncOpenAI

from apeiria.app.ai.model.adapter import (
    AIModelCatalogItem,
    AIModelGenerateRequest,
    AIModelGenerateResponse,
    AIModelToolCall,
)


class OpenAICompatibleProviderConfigError(RuntimeError):
    """Raised when required OpenAI-compatible settings are missing."""

    def __init__(self, field_name: str) -> None:
        super().__init__(f"openai-compatible source requires {field_name}")


class OpenAICompatibleProvider:
    """OpenAI-compatible text generation adapter backed by the official SDK."""

    def __init__(
        self,
        *,
        api_base: str | None,
        api_key: str | None = None,
        request_func: Any | None = None,
        list_request_func: Any | None = None,
    ) -> None:
        self.api_base = _normalize_openai_api_base(api_base)
        self.api_key = api_key
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

        client = AsyncOpenAI(api_key=api_key, base_url=api_base)
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

        client = AsyncOpenAI(api_key=resolved_api_key, base_url=self.api_base)
        try:
            page = await client.models.list()
        finally:
            await client.close()
        return _extract_openai_models(page)


def _coerce_str(extra: dict[str, Any] | None, key: str) -> str | None:
    if not extra:
        return None
    value = extra.get(key)
    return value if isinstance(value, str) and value.strip() else None


def _normalize_openai_api_base(api_base: str | None) -> str | None:
    if not isinstance(api_base, str) or not api_base.strip():
        return None
    return api_base.strip().rstrip("/")


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
