"""Factory for building concrete provider adapters from provider definitions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from apeiria.app.ai.model.adapters import (
    AnthropicCompatibleProvider,
    OpenAICompatibleProvider,
)

if TYPE_CHECKING:
    from apeiria.app.ai.model.provider import AIModelProvider
    from apeiria.app.ai.model.providers import AIProviderDefinition


class UnsupportedAIProviderTypeError(RuntimeError):
    """Raised when no concrete adapter exists for a provider type."""

    def __init__(self, provider_type: str) -> None:
        super().__init__(f"provider type '{provider_type}' is not supported")


def build_provider_adapter(
    provider: "AIProviderDefinition",
    *,
    api_key: str | None = None,
    request_func: Any | None = None,
) -> "AIModelProvider":
    """Build a concrete provider adapter from a provider definition."""

    if provider.provider_type in {"openai_compatible", "litellm"}:
        return OpenAICompatibleProvider(
            api_base=provider.api_base,
            api_key=api_key,
            request_func=request_func,
        )
    if provider.provider_type in {"anthropic", "anthropic_compatible"}:
        return AnthropicCompatibleProvider(
            api_base=provider.api_base,
            api_key=api_key,
            request_func=request_func,
        )
    raise UnsupportedAIProviderTypeError(provider.provider_type)
