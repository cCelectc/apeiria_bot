"""AI source domain models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from apeiria.ai.model.runtime.capabilities import AIModelAdapterKind

AISourceCapabilityType = Literal[
    "chat_completion",
    "embedding",
    "speech_to_text",
    "text_to_speech",
    "rerank",
]
AISourceClientType = Literal[
    "openai",
    "anthropic",
    "generic_rerank",
    "gemini",
    "ollama",
]
AISourcePresetType = Literal[
    "openai_compatible",
    "openai_compatible_embedding",
    "openai_compatible_stt",
    "openai_compatible_tts",
    "generic_rerank_api",
    "anthropic_compatible",
    "gemini_native",
    "gemini_native_embedding",
    "ollama_native",
    "ollama_native_embedding",
]


class UnsupportedAISourcePresetError(ValueError):
    """Raised when no known source preset can be resolved."""


@dataclass(frozen=True)
class AISourcePresetDefinition:
    """One source preset exposed to the owner-facing admin UI."""

    preset_type: AISourcePresetType
    display_name: str
    capability_type: AISourceCapabilityType
    client_type: AISourceClientType
    adapter_kind: AIModelAdapterKind
    default_api_base: str | None
    description: str
    capability_metadata: dict[str, Any] | None = None
    default_options: dict[str, Any] | None = None
    capability_provenance: dict[str, Any] | None = None


@dataclass(frozen=True)
class AISourceDefinition:
    """One configured upstream source."""

    source_id: str
    name: str
    capability_type: AISourceCapabilityType
    client_type: AISourceClientType
    preset_type: AISourcePresetType
    api_base: str | None
    enabled: bool = True
    timeout_seconds: int | None = None
    custom_headers: dict[str, str] | None = None
    extra_config: dict[str, Any] | None = None
    adapter_kind: AIModelAdapterKind | None = None
    capability_metadata: dict[str, Any] | None = None
    default_options: dict[str, Any] | None = None
    capability_provenance: dict[str, Any] | None = None


SOURCE_PRESETS: tuple[AISourcePresetDefinition, ...] = (
    AISourcePresetDefinition(
        preset_type="openai_compatible",
        display_name="OpenAI Compatible",
        capability_type="chat_completion",
        client_type="openai",
        adapter_kind="openai_compatible",
        default_api_base=None,
        description="适用于 OpenAI 风格的聊天补全接口。",
    ),
    AISourcePresetDefinition(
        preset_type="openai_compatible_embedding",
        display_name="OpenAI Compatible",
        capability_type="embedding",
        client_type="openai",
        adapter_kind="openai_compatible",
        default_api_base=None,
        description="适用于 OpenAI 风格的嵌入接口。",
    ),
    AISourcePresetDefinition(
        preset_type="openai_compatible_stt",
        display_name="OpenAI Compatible",
        capability_type="speech_to_text",
        client_type="openai",
        adapter_kind="openai_compatible",
        default_api_base=None,
        description="适用于 OpenAI 风格的语音转文字接口。",
    ),
    AISourcePresetDefinition(
        preset_type="openai_compatible_tts",
        display_name="OpenAI Compatible",
        capability_type="text_to_speech",
        client_type="openai",
        adapter_kind="openai_compatible",
        default_api_base=None,
        description="适用于 OpenAI 风格的文字转语音接口。",
    ),
    AISourcePresetDefinition(
        preset_type="generic_rerank_api",
        display_name="Generic Rerank API",
        capability_type="rerank",
        client_type="generic_rerank",
        adapter_kind="generic_rerank",
        default_api_base="http://127.0.0.1:8000",
        description="适用于常见 `/rerank` 风格的重排序接口。",
    ),
    AISourcePresetDefinition(
        preset_type="anthropic_compatible",
        display_name="Anthropic Compatible",
        capability_type="chat_completion",
        client_type="anthropic",
        adapter_kind="anthropic_compatible",
        default_api_base=None,
        description="适用于 Anthropic 风格的消息接口。",
    ),
    AISourcePresetDefinition(
        preset_type="gemini_native",
        display_name="Gemini Native",
        capability_type="chat_completion",
        client_type="gemini",
        adapter_kind="gemini_native",
        default_api_base=None,
        description="适用于 Gemini 原生生成内容接口。",
    ),
    AISourcePresetDefinition(
        preset_type="gemini_native_embedding",
        display_name="Gemini Native",
        capability_type="embedding",
        client_type="gemini",
        adapter_kind="gemini_native",
        default_api_base=None,
        description="适用于 Gemini 原生嵌入接口。",
    ),
    AISourcePresetDefinition(
        preset_type="ollama_native",
        display_name="Ollama Native",
        capability_type="chat_completion",
        client_type="ollama",
        adapter_kind="ollama_native",
        default_api_base="http://127.0.0.1:11434",
        description="适用于 Ollama 本地原生聊天接口。",
    ),
    AISourcePresetDefinition(
        preset_type="ollama_native_embedding",
        display_name="Ollama Native",
        capability_type="embedding",
        client_type="ollama",
        adapter_kind="ollama_native",
        default_api_base="http://127.0.0.1:11434",
        description="适用于 Ollama 本地原生嵌入接口。",
    ),
)

CLIENT_TYPE_ADAPTER_KIND_MAP: dict[AISourceClientType, AIModelAdapterKind] = {
    "openai": "openai_compatible",
    "anthropic": "anthropic_compatible",
    "generic_rerank": "generic_rerank",
    "gemini": "gemini_native",
    "ollama": "ollama_native",
}


def resolve_client_type_for_preset(
    preset_type: AISourcePresetType,
) -> AISourceClientType:
    for item in SOURCE_PRESETS:
        if item.preset_type == preset_type:
            return item.client_type
    raise UnsupportedAISourcePresetError


def resolve_adapter_kind_for_client_type(
    client_type: AISourceClientType,
) -> AIModelAdapterKind:
    """Bridge legacy client type values into adapter-kind vocabulary."""

    return CLIENT_TYPE_ADAPTER_KIND_MAP[client_type]


def resolve_adapter_kind_for_preset(
    preset_type: AISourcePresetType,
) -> AIModelAdapterKind:
    for item in SOURCE_PRESETS:
        if item.preset_type == preset_type:
            return item.adapter_kind
    raise UnsupportedAISourcePresetError


def resolve_capability_type_for_preset(
    preset_type: AISourcePresetType,
) -> AISourceCapabilityType:
    for item in SOURCE_PRESETS:
        if item.preset_type == preset_type:
            return item.capability_type
    raise UnsupportedAISourcePresetError
