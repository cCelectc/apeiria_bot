"""Schema models for AI source routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from apeiria.ai.model import AISourceDefinition, AISourcePresetDefinition

_SHORT_API_KEY_MAX_LENGTH = 8


class AISourcePresetItem(BaseModel):
    preset_type: str
    display_name: str
    capability_type: str
    client_type: str
    adapter_kind: str
    description: str
    capability_metadata: dict[str, object] = {}
    default_options: dict[str, object] = {}
    capability_provenance: dict[str, object] = {}


class AIBootstrapResponse(BaseModel):
    source_presets: list["AISourcePresetItem"] = []
    scope_types: list[str] = []
    task_classes: list[str] = []


class AIRuntimeStatusResponse(BaseModel):
    configuration_api_available: bool = True
    runtime_plugin_module: str
    runtime_plugin_enabled: bool
    runtime_plugin_loaded: bool
    lifecycle_initialized: bool
    lifecycle_source: str
    runtime_ready: bool
    runtime_phase: str
    runtime_summary: str


class AISourceApiKeyMetadata(BaseModel):
    index: int
    masked: str


class AISourceItem(BaseModel):
    source_id: str
    name: str
    capability_type: str
    client_type: str
    adapter_kind: str | None = None
    preset_type: str
    api_base: str | None = None
    enabled: bool
    timeout_seconds: int | None = None
    custom_headers: dict[str, str] = {}
    extra_config: dict[str, object] = {}
    capability_metadata: dict[str, object] = {}
    default_options: dict[str, object] = {}
    capability_provenance: dict[str, object] = {}
    api_key_metadata: list[AISourceApiKeyMetadata] = []


class AISourceUpsertRequest(BaseModel):
    source_id: str | None = None
    name: str = Field(min_length=1, max_length=128)
    capability_type: str = Field(min_length=1, max_length=32)
    preset_type: str = Field(min_length=1, max_length=64)
    api_base: str | None = Field(default=None, max_length=2000)
    enabled: bool = True
    timeout_seconds: int | None = Field(default=None, ge=1, le=600)
    custom_headers: dict[str, str] = {}
    extra_config: dict[str, object] = {}
    adapter_kind: str | None = Field(default=None, max_length=64)
    capability_metadata: dict[str, object] = {}
    default_options: dict[str, object] = {}
    capability_provenance: dict[str, object] = {}
    api_key_action: Literal["keep", "replace", "clear"] | None = None
    api_keys: list[str] = []


def to_ai_source_preset_item(item: "AISourcePresetDefinition") -> AISourcePresetItem:
    return AISourcePresetItem(
        preset_type=item.preset_type,
        display_name=item.display_name,
        capability_type=item.capability_type,
        client_type=item.client_type,
        adapter_kind=item.adapter_kind,
        description=item.description,
        capability_metadata=item.capability_metadata or {},
        default_options=item.default_options or {},
        capability_provenance=item.capability_provenance or {},
    )


def to_ai_source_item(item: "AISourceDefinition") -> AISourceItem:
    return AISourceItem(
        source_id=item.source_id,
        name=item.name,
        capability_type=item.capability_type,
        client_type=item.client_type,
        adapter_kind=item.adapter_kind,
        preset_type=item.preset_type,
        api_base=item.api_base,
        enabled=item.enabled,
        timeout_seconds=item.timeout_seconds,
        custom_headers=item.custom_headers or {},
        extra_config=_public_extra_config(item.extra_config),
        capability_metadata=item.capability_metadata or {},
        default_options=item.default_options or {},
        capability_provenance=item.capability_provenance or {},
        api_key_metadata=_api_key_metadata(item.extra_config),
    )


def _public_extra_config(extra_config: dict[str, object] | None) -> dict[str, object]:
    public_config = dict(extra_config or {})
    public_config.pop("api_keys", None)
    return public_config


def _api_key_metadata(
    extra_config: dict[str, object] | None,
) -> list[AISourceApiKeyMetadata]:
    return [
        AISourceApiKeyMetadata(index=index, masked=_mask_api_key(value))
        for index, value in enumerate(_api_key_values(extra_config))
    ]


def _api_key_values(extra_config: dict[str, object] | None) -> list[str]:
    raw_values = (extra_config or {}).get("api_keys")
    if not isinstance(raw_values, list):
        return []
    return [
        value.strip()
        for value in raw_values
        if isinstance(value, str) and value.strip()
    ]


def _mask_api_key(value: str) -> str:
    if len(value) <= _SHORT_API_KEY_MAX_LENGTH:
        return "****"
    return f"{value[:4]}...{value[-4:]}"
