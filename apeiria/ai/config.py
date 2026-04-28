"""Configuration model for the AI plugin runtime."""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from apeiria.config import project_config_service

ModelT = TypeVar("ModelT", bound=BaseModel)


class AIPluginConfig(BaseModel):
    """Runtime configuration for the AI plugin."""

    allow_group_initiative: bool = False
    persist_raw_event_payloads: bool = False
    ambient_merge_window_ms: int = 1500
    max_pending_messages: int = 12
    group_reply_cooldown_seconds: int = 180
    max_consecutive_ambient_replies: int = 1
    direct_bypass_ambient_budget: bool = True
    duplicate_event_ttl_seconds: int = 30
    tool_execution_timeout_seconds: float = 8.0
    cleanup_interval_minutes: int = 30
    conversation_retention_days: int = 30
    raw_event_retention_days: int = 7
    tool_execution_retention_days: int = 30
    ignored_memory_retention_days: int = 30


def _validate_config(model: type[ModelT], data: dict[str, object]) -> ModelT:
    return model.model_validate(data)


def get_ai_plugin_config() -> AIPluginConfig:
    """Read AI plugin configuration from project plugin config."""

    return _validate_config(
        AIPluginConfig,
        project_config_service.read_project_plugin_config("ai"),
    )
