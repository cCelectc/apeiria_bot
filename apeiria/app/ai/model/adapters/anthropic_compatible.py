"""Anthropic-compatible source adapter."""

from __future__ import annotations

from typing import Any

from anthropic import AsyncAnthropic

from apeiria.app.ai.model.adapter import (
    AIModelCatalogItem,
    AIModelGenerateRequest,
    AIModelGenerateResponse,
    AIModelToolCall,
)


class AnthropicCompatibleProviderConfigError(RuntimeError):
    """Raised when required Anthropic-compatible settings are missing."""

    def __init__(self, field_name: str) -> None:
        super().__init__(f"anthropic-compatible source requires {field_name}")


class AnthropicCompatibleProvider:
    """Anthropic-compatible text generation adapter backed by the official SDK."""

    def __init__(
        self,
        *,
        api_base: str | None,
        api_key: str | None = None,
        request_func: Any | None = None,
        list_request_func: Any | None = None,
    ) -> None:
        self.api_base = _normalize_anthropic_api_base(api_base)
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
        if request.tools:
            payload["tools"] = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.parameters,
                }
                for tool in request.tools
            ]

        client = AsyncAnthropic(api_key=api_key, base_url=api_base)
        try:
            response = await client.messages.create(**payload)
        finally:
            await client.close()
        raw = response.model_dump(mode="json")
        return AIModelGenerateResponse(
            source_id=request.source_id,
            model_name=request.model_name,
            content=_extract_anthropic_content(response),
            tool_calls=tuple(_extract_anthropic_tool_calls(response)),
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

        client = AsyncAnthropic(api_key=resolved_api_key, base_url=self.api_base)
        try:
            page = await client.models.list()
        finally:
            await client.close()
        return _extract_anthropic_models(page)


def _coerce_str(extra: dict[str, Any] | None, key: str) -> str | None:
    if not extra:
        return None
    value = extra.get(key)
    return value if isinstance(value, str) and value.strip() else None


def _normalize_anthropic_api_base(api_base: str | None) -> str | None:
    if not isinstance(api_base, str) or not api_base.strip():
        return None
    return api_base.strip().rstrip("/")


def _extract_anthropic_content(response: Any) -> str:
    content = getattr(response, "content", None)
    if not isinstance(content, list):
        return ""
    for block in content:
        if getattr(block, "type", None) == "text":
            text = getattr(block, "text", None)
            if isinstance(text, str):
                return text
    return ""


def _extract_anthropic_models(page: Any) -> list[AIModelCatalogItem]:
    rows = getattr(page, "data", None)
    if not isinstance(rows, list):
        return []
    models: list[AIModelCatalogItem] = []
    for row in rows:
        model_id = getattr(row, "id", None)
        if not isinstance(model_id, str):
            continue
        display_name = getattr(row, "display_name", None)
        models.append(
            AIModelCatalogItem(
                id=model_id,
                name=display_name if isinstance(display_name, str) else model_id,
            )
        )
    return models


def _extract_anthropic_tool_calls(response: Any) -> list[AIModelToolCall]:
    content = getattr(response, "content", None)
    if not isinstance(content, list):
        return []

    extracted: list[AIModelToolCall] = []
    for index, block in enumerate(content):
        if getattr(block, "type", None) != "tool_use":
            continue
        name = getattr(block, "name", None)
        if not isinstance(name, str) or not name.strip():
            continue
        input_payload = getattr(block, "input", None)
        extracted.append(
            AIModelToolCall(
                tool_call_id=str(getattr(block, "id", None) or f"tool_call_{index}"),
                name=name,
                arguments=input_payload if isinstance(input_payload, dict) else {},
            )
        )
    return extracted
