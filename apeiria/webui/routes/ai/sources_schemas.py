"""Schema models for AI source routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from apeiria.ai.model import AISourceDefinition, AISourcePresetDefinition


class AISourcePresetItem(BaseModel):
    preset_type: str
    display_name: str
    capability_type: str
    client_type: str
    default_api_base: str | None = None
    description: str


class AIBootstrapResponse(BaseModel):
    source_presets: list["AISourcePresetItem"] = []
    scope_types: list[str] = []
    capability_modes: list[str] = []
    task_classes: list[str] = []


class AISourceItem(BaseModel):
    source_id: str
    name: str
    capability_type: str
    client_type: str
    preset_type: str
    api_base: str | None = None
    api_key_env_name: str | None = None
    enabled: bool
    timeout_seconds: int | None = None
    custom_headers: dict[str, str] = {}
    extra_config: dict[str, object] = {}


class AISourceUpsertRequest(BaseModel):
    source_id: str | None = None
    name: str = Field(min_length=1, max_length=128)
    capability_type: str = Field(min_length=1, max_length=32)
    preset_type: str = Field(min_length=1, max_length=64)
    api_base: str | None = Field(default=None, max_length=2000)
    api_key_env_name: str | None = Field(default=None, max_length=128)
    enabled: bool = True
    timeout_seconds: int | None = Field(default=None, ge=1, le=600)
    custom_headers: dict[str, str] = {}
    extra_config: dict[str, object] = {}


def to_ai_source_preset_item(item: "AISourcePresetDefinition") -> AISourcePresetItem:
    return AISourcePresetItem(
        preset_type=item.preset_type,
        display_name=item.display_name,
        capability_type=item.capability_type,
        client_type=item.client_type,
        default_api_base=item.default_api_base,
        description=item.description,
    )


def to_ai_source_item(item: "AISourceDefinition") -> AISourceItem:
    return AISourceItem(
        source_id=item.source_id,
        name=item.name,
        capability_type=item.capability_type,
        client_type=item.client_type,
        preset_type=item.preset_type,
        api_base=item.api_base,
        api_key_env_name=item.api_key_env_name,
        enabled=item.enabled,
        timeout_seconds=item.timeout_seconds,
        custom_headers=item.custom_headers or {},
        extra_config=item.extra_config or {},
    )
