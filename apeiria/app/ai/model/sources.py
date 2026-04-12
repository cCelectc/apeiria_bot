"""AI source domain models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

AISourceCapabilityType = Literal["chat_completion"]
AISourceClientType = Literal["openai", "anthropic"]
AISourcePresetType = Literal["openai_compatible", "anthropic_compatible"]


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
        default_api_base=None,
        description="适用于 OpenAI 风格的聊天补全接口。",
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
