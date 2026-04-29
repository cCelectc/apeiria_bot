"""Factory for building concrete source adapters from source definitions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from apeiria.ai.model.runtime.registry import (
    UnsupportedAIModelAdapterKindError,
    provider_adapter_registry,
)
from apeiria.ai.model.sources.models import resolve_adapter_kind_for_client_type

if TYPE_CHECKING:
    from apeiria.ai.model.runtime.adapter import AIModelAdapter
    from apeiria.ai.model.sources.models import AISourceDefinition

SUPPORTED_SOURCE_CLIENT_TYPES = ("openai", "anthropic", "generic_rerank")
SUPPORTED_MODEL_ADAPTER_KINDS = (
    "openai_compatible",
    "anthropic_compatible",
    "generic_rerank",
)


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

    adapter_kind = source.adapter_kind or resolve_adapter_kind_for_client_type(
        source.client_type
    )
    try:
        entry = provider_adapter_registry.get(adapter_kind)
    except UnsupportedAIModelAdapterKindError as exc:
        raise UnsupportedAIModelAdapterKindError(adapter_kind) from exc
    return entry.factory(
        api_base=source.api_base,
        api_key=api_key,
        timeout_seconds=source.timeout_seconds,
        extra_config=extra_config,
        request_func=request_func,
    )
