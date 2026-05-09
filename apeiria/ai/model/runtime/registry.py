"""Provider adapter registry keyed by runtime adapter kind."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from apeiria.ai.model.runtime.capabilities import (
    AIModelAdapterKind,
    AIModelCapabilities,
)

if TYPE_CHECKING:
    from apeiria.ai.model.runtime.adapter import AIModelAdapter


class ProviderAdapterFactory(Protocol):
    """Factory callable used by provider adapter registry entries."""

    def __call__(
        self,
        *,
        api_base: str | None,
        api_key: str | None = None,
        timeout_seconds: int | None = None,
        extra_config: dict[str, Any] | None = None,
        request_func: Any | None = None,
    ) -> "AIModelAdapter": ...


@dataclass(frozen=True)
class ProviderOperationSupport:
    """Operations one adapter family can perform."""

    chat: bool = False
    embedding: bool = False
    speech_to_text: bool = False
    text_to_speech: bool = False
    rerank: bool = False
    list_models: bool = True


@dataclass(frozen=True)
class ProviderAdapterRegistryEntry:
    """One provider protocol entry."""

    adapter_kind: AIModelAdapterKind
    display_name: str
    factory: ProviderAdapterFactory
    operation_support: ProviderOperationSupport
    default_capabilities: AIModelCapabilities
    supported_options: frozenset[str] = frozenset()


class UnsupportedAIModelAdapterKindError(RuntimeError):
    """Raised when a provider adapter kind is not registered."""

    def __init__(self, adapter_kind: str) -> None:
        super().__init__(f"model adapter kind '{adapter_kind}' is not supported")


class ProviderAdapterRegistry:
    """In-memory registry of provider protocol implementations."""

    def __init__(
        self,
        entries: tuple[ProviderAdapterRegistryEntry, ...] = (),
    ) -> None:
        self._entries: dict[str, ProviderAdapterRegistryEntry] = {}
        for entry in entries:
            self.register(entry)

    def register(self, entry: ProviderAdapterRegistryEntry) -> None:
        self._entries[entry.adapter_kind] = entry

    def get(self, adapter_kind: str | None) -> ProviderAdapterRegistryEntry:
        if adapter_kind is None:
            raise UnsupportedAIModelAdapterKindError("<missing>")
        entry = self._entries.get(adapter_kind)
        if entry is None:
            raise UnsupportedAIModelAdapterKindError(adapter_kind)
        return entry

    def list_entries(self) -> tuple[ProviderAdapterRegistryEntry, ...]:
        return tuple(self._entries.values())


UnsupportedProviderAdapterKindError = UnsupportedAIModelAdapterKindError


def _build_default_registry() -> ProviderAdapterRegistry:
    from apeiria.ai.model.adapters import (
        AnthropicCompatibleProvider,
        GeminiNativeProvider,
        GenericRerankProvider,
        OllamaNativeProvider,
        OpenAICompatibleProvider,
    )

    return ProviderAdapterRegistry(
        (
            ProviderAdapterRegistryEntry(
                adapter_kind="openai_compatible",
                display_name="OpenAI Compatible",
                factory=OpenAICompatibleProvider,
                operation_support=ProviderOperationSupport(
                    chat=True,
                    embedding=True,
                    speech_to_text=True,
                    text_to_speech=True,
                ),
                default_capabilities=AIModelCapabilities(
                    lanes=frozenset(
                        {
                            "chat_completion",
                            "embedding",
                            "speech_to_text",
                            "text_to_speech",
                        }
                    ),
                    input_modalities=frozenset({"text"}),
                    output_modalities=frozenset({"text"}),
                    supports_tool_calling=True,
                    supported_options=frozenset(
                        {"temperature", "max_tokens", "api_base", "api_key"}
                    ),
                ),
                supported_options=frozenset(
                    {"temperature", "max_tokens", "api_base", "api_key"}
                ),
            ),
            ProviderAdapterRegistryEntry(
                adapter_kind="anthropic_compatible",
                display_name="Anthropic Compatible",
                factory=AnthropicCompatibleProvider,
                operation_support=ProviderOperationSupport(chat=True),
                default_capabilities=AIModelCapabilities(
                    lanes=frozenset({"chat_completion"}),
                    input_modalities=frozenset({"text"}),
                    output_modalities=frozenset({"text"}),
                    supports_tool_calling=True,
                    supported_options=frozenset(
                        {"temperature", "max_tokens", "api_base", "api_key"}
                    ),
                ),
                supported_options=frozenset(
                    {"temperature", "max_tokens", "api_base", "api_key"}
                ),
            ),
            ProviderAdapterRegistryEntry(
                adapter_kind="generic_rerank",
                display_name="Generic Rerank",
                factory=GenericRerankProvider,
                operation_support=ProviderOperationSupport(rerank=True),
                default_capabilities=AIModelCapabilities(
                    lanes=frozenset({"rerank"}),
                    input_modalities=frozenset({"text"}),
                    output_modalities=frozenset({"text"}),
                    supported_options=frozenset(
                        {"api_key", "api_suffix", "top_n", "proxy"}
                    ),
                ),
                supported_options=frozenset(
                    {"api_key", "api_suffix", "top_n", "proxy"}
                ),
            ),
            ProviderAdapterRegistryEntry(
                adapter_kind="gemini_native",
                display_name="Gemini Native",
                factory=GeminiNativeProvider,
                operation_support=ProviderOperationSupport(
                    chat=True,
                    embedding=True,
                ),
                default_capabilities=AIModelCapabilities(
                    lanes=frozenset({"chat_completion", "embedding"}),
                    input_modalities=frozenset({"text"}),
                    output_modalities=frozenset({"text"}),
                    supports_tool_calling=False,
                    supported_options=frozenset(
                        {"temperature", "max_tokens", "api_base", "api_key"}
                    ),
                ),
                supported_options=frozenset(
                    {"temperature", "max_tokens", "api_base", "api_key"}
                ),
            ),
            ProviderAdapterRegistryEntry(
                adapter_kind="ollama_native",
                display_name="Ollama Native",
                factory=OllamaNativeProvider,
                operation_support=ProviderOperationSupport(
                    chat=True,
                    embedding=True,
                ),
                default_capabilities=AIModelCapabilities(
                    lanes=frozenset({"chat_completion", "embedding"}),
                    input_modalities=frozenset({"text"}),
                    output_modalities=frozenset({"text"}),
                    supports_tool_calling=False,
                    supported_options=frozenset(
                        {"temperature", "max_tokens", "api_base", "api_key"}
                    ),
                ),
                supported_options=frozenset(
                    {"temperature", "max_tokens", "api_base", "api_key"}
                ),
            ),
        )
    )


provider_adapter_registry = _build_default_registry()
