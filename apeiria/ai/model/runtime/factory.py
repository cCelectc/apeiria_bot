"""Factory for building concrete source adapters from source definitions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from apeiria.ai.model.adapters import (
    AnthropicCompatibleProvider,
    GenericRerankProvider,
    OpenAICompatibleProvider,
)

if TYPE_CHECKING:
    from apeiria.ai.model.runtime.adapter import AIModelAdapter
    from apeiria.ai.model.sources.models import AISourceDefinition

SUPPORTED_SOURCE_CLIENT_TYPES = ("openai", "anthropic", "generic_rerank")


class UnsupportedAISourceClientTypeError(RuntimeError):
    """Raised when no concrete adapter exists for a source client type."""

    def __init__(self, client_type: str) -> None:
        super().__init__(f"source client type '{client_type}' is not supported")


def build_source_adapter(
    source: "AISourceDefinition",
    *,
    api_key: str | None = None,
    request_func: Any | None = None,
) -> "AIModelAdapter":
    """Build a concrete source adapter from one source definition."""

    extra_config = dict(source.extra_config or {})
    if source.custom_headers:
        extra_config["_custom_headers"] = dict(source.custom_headers)

    if source.client_type == "openai":
        return OpenAICompatibleProvider(
            api_base=source.api_base,
            api_key=api_key,
            timeout_seconds=source.timeout_seconds,
            extra_config=extra_config,
            request_func=request_func,
        )
    if source.client_type == "anthropic":
        return AnthropicCompatibleProvider(
            api_base=source.api_base,
            api_key=api_key,
            timeout_seconds=source.timeout_seconds,
            extra_config=extra_config,
            request_func=request_func,
        )
    if source.client_type == "generic_rerank":
        return GenericRerankProvider(
            api_base=source.api_base,
            api_key=api_key,
            timeout_seconds=source.timeout_seconds,
            extra_config=extra_config,
            request_func=request_func,
        )
    raise UnsupportedAISourceClientTypeError(source.client_type)
