"""AI source domain models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

AISourceCapabilityType = Literal[
    "chat_completion",
    "embedding",
    "speech_to_text",
    "text_to_speech",
    "rerank",
]
AISourceClientType = Literal["openai", "anthropic", "generic_rerank"]
AISourcePresetType = Literal[
    "openai_compatible",
    "openai_compatible_embedding",
    "openai_compatible_stt",
    "openai_compatible_tts",
    "generic_rerank_api",
    "anthropic_compatible",
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
    default_api_base: str | None
    description: str


@dataclass(frozen=True)
class AISourceDefinition:
    """One configured upstream source."""

    source_id: str
    name: str
    capability_type: AISourceCapabilityType
    client_type: AISourceClientType
    preset_type: AISourcePresetType
    api_base: str | None
    api_key_env_name: str | None = None
    enabled: bool = True
    timeout_seconds: int | None = None
    custom_headers: dict[str, str] | None = None
    extra_config: dict[str, Any] | None = None


SOURCE_PRESETS: tuple[AISourcePresetDefinition, ...] = (
    AISourcePresetDefinition(
        preset_type="openai_compatible",
        display_name="OpenAI Compatible",
        capability_type="chat_completion",
        client_type="openai",
        default_api_base="https://api.openai.com/v1",
        description="适用于 OpenAI 风格的聊天补全接口。",
    ),
    AISourcePresetDefinition(
        preset_type="openai_compatible_embedding",
        display_name="OpenAI Compatible",
        capability_type="embedding",
        client_type="openai",
        default_api_base="https://api.openai.com/v1",
        description="适用于 OpenAI 风格的嵌入接口。",
    ),
    AISourcePresetDefinition(
        preset_type="openai_compatible_stt",
        display_name="OpenAI Compatible",
        capability_type="speech_to_text",
        client_type="openai",
        default_api_base="https://api.openai.com/v1",
        description="适用于 OpenAI 风格的语音转文字接口。",
    ),
    AISourcePresetDefinition(
        preset_type="openai_compatible_tts",
        display_name="OpenAI Compatible",
        capability_type="text_to_speech",
        client_type="openai",
        default_api_base="https://api.openai.com/v1",
        description="适用于 OpenAI 风格的文字转语音接口。",
    ),
    AISourcePresetDefinition(
        preset_type="generic_rerank_api",
        display_name="Generic Rerank API",
        capability_type="rerank",
        client_type="generic_rerank",
        default_api_base="http://127.0.0.1:8000",
        description="适用于常见 `/rerank` 风格的重排序接口。",
    ),
    AISourcePresetDefinition(
        preset_type="anthropic_compatible",
        display_name="Anthropic Compatible",
        capability_type="chat_completion",
        client_type="anthropic",
        default_api_base=None,
        description="适用于 Anthropic 风格的消息接口。",
    ),
)


def resolve_client_type_for_preset(
    preset_type: AISourcePresetType,
) -> AISourceClientType:
    for item in SOURCE_PRESETS:
        if item.preset_type == preset_type:
            return item.client_type
    raise UnsupportedAISourcePresetError
