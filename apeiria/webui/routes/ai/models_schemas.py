"""Schema models for AI source-model and model-profile routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from apeiria.ai.model import (
        AIModelBindingSpec,
        AIModelProfileDefinition,
        AISourceModelDefinition,
    )
    from apeiria.ai.model import AIModelCatalogItem as DomainModelCatalogItem


class AISourceModelFetchRequest(BaseModel):
    source_id: str | None = Field(default=None, max_length=64)
    preset_type: str | None = Field(default=None, max_length=64)
    api_base: str | None = Field(default=None, max_length=2000)
    api_key_env_name: str | None = Field(default=None, max_length=128)
    api_key: str | None = Field(default=None, max_length=512)
    extra_config: dict[str, object] = {}


class AISourceModelTestRequest(BaseModel):
    source_id: str | None = Field(default=None, max_length=64)
    preset_type: str | None = Field(default=None, max_length=64)
    api_base: str | None = Field(default=None, max_length=2000)
    api_key_env_name: str | None = Field(default=None, max_length=128)
    api_key: str | None = Field(default=None, max_length=512)
    extra_config: dict[str, object] = {}
    model_identifier: str = Field(min_length=1, max_length=256)


class AISourceModelTestResult(BaseModel):
    model_identifier: str
    content: str
    tool_call_count: int


class AISourceModelItem(BaseModel):
    model_id: str
    source_id: str
    model_identifier: str
    display_name: str
    enabled: bool
    is_default: bool
    extra_params: dict[str, object] = {}


class AISourceModelUpsertRequest(BaseModel):
    model_id: str | None = None
    source_id: str = Field(min_length=1, max_length=64)
    model_identifier: str = Field(min_length=1, max_length=256)
    display_name: str = Field(min_length=1, max_length=128)
    enabled: bool = True
    is_default: bool = False
    extra_params: dict[str, object] = {}


class AIModelProfileItem(BaseModel):
    profile_id: str
    name: str
    model_id: str
    task_class: str
    priority: int
    enabled: bool
    fallback_profile_id: str | None = None


class AIModelProfileUpsertRequest(BaseModel):
    profile_id: str | None = None
    name: str = Field(min_length=1, max_length=128)
    model_id: str = Field(min_length=1, max_length=64)
    task_class: str = Field(min_length=1, max_length=64)
    priority: int = Field(default=100, ge=0, le=10000)
    enabled: bool = True
    fallback_profile_id: str | None = Field(default=None, max_length=64)


class AIModelBindingItem(BaseModel):
    binding_id: str
    scope_type: str
    scope_id: str
    profile_id: str


class AIModelCatalogItem(BaseModel):
    id: str
    name: str


def to_ai_source_model_item(item: "AISourceModelDefinition") -> AISourceModelItem:
    return AISourceModelItem(
        model_id=item.model_id,
        source_id=item.source_id,
        model_identifier=item.model_identifier,
        display_name=item.display_name,
        enabled=item.enabled,
        is_default=item.is_default,
        extra_params=item.extra_params or {},
    )


def to_ai_model_profile_item(item: "AIModelProfileDefinition") -> AIModelProfileItem:
    return AIModelProfileItem(
        profile_id=item.profile_id,
        name=item.name,
        model_id=item.model_id or "",
        task_class=item.task_class,
        priority=item.priority,
        enabled=item.enabled,
        fallback_profile_id=item.fallback_profile_id,
    )


def to_ai_model_binding_item(item: "AIModelBindingSpec") -> AIModelBindingItem:
    return AIModelBindingItem(
        binding_id=item.binding_id,
        scope_type=item.scope_type,
        scope_id=item.scope_id,
        profile_id=item.profile_id,
    )


def to_ai_model_catalog_item(item: "DomainModelCatalogItem") -> AIModelCatalogItem:
    return AIModelCatalogItem(
        id=item.id,
        name=item.name,
    )
