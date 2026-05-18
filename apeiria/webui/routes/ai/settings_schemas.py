"""Schema models for AI runtime settings routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from apeiria.ai.runtime_settings import (
        AIRuntimeSettingField,
        AIRuntimeSettingsView,
    )


class AIRuntimeSettingFieldItem(BaseModel):
    key: str
    label: str
    help: str
    group: str
    value_type: str
    application: str
    minimum: float | None = None
    default_value: object | None = None
    current_value: object | None = None
    local_value: object | None = None
    has_local_override: bool = False


class AIRuntimeSettingsResponse(BaseModel):
    effective: dict[str, object]
    defaults: dict[str, object]
    overrides: dict[str, object]
    fields: list[AIRuntimeSettingFieldItem]
    updated_at: str | None = None


class AIRuntimeSettingsUpdateRequest(BaseModel):
    values: dict[str, object] = Field(default_factory=dict)
    clear: list[str] = Field(default_factory=list)


def to_ai_runtime_settings_response(
    view: "AIRuntimeSettingsView",
) -> AIRuntimeSettingsResponse:
    effective = view.effective.model_dump(mode="python")
    defaults = view.defaults.model_dump(mode="python")
    overrides = {str(key): value for key, value in view.overrides.items()}
    return AIRuntimeSettingsResponse(
        effective=effective,
        defaults=defaults,
        overrides=overrides,
        fields=[
            _to_setting_field_item(
                item,
                effective=effective,
                defaults=defaults,
                overrides=overrides,
            )
            for item in view.fields
        ],
        updated_at=view.updated_at,
    )


def _to_setting_field_item(
    item: "AIRuntimeSettingField",
    *,
    effective: dict[str, object],
    defaults: dict[str, object],
    overrides: dict[str, object],
) -> AIRuntimeSettingFieldItem:
    key = item.key
    return AIRuntimeSettingFieldItem(
        key=key,
        label=item.label,
        help=item.help,
        group=item.group,
        value_type=item.value_type,
        application=item.application,
        minimum=item.minimum,
        default_value=defaults.get(key),
        current_value=effective.get(key),
        local_value=overrides.get(key),
        has_local_override=key in overrides,
    )
