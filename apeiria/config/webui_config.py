from __future__ import annotations

"""Configuration model for the Web UI plugin."""

from typing import TypeVar

from pydantic import BaseModel

from .project import project_config_service

ModelT = TypeVar("ModelT", bound=BaseModel)


class WebUIConfig(BaseModel):
    """Runtime configuration for the Web UI plugin."""

    token_expire_days: int = 7


def _validate_config(model: type[ModelT], data: dict[str, object]) -> ModelT:
    """Validate plugin config data against a Pydantic model."""
    return model.model_validate(data)


def get_web_ui_config() -> WebUIConfig:
    """Read Web UI config with a fallback for the legacy project key."""
    config = project_config_service.read_project_plugin_config("web_ui")
    if "token_expire_days" not in config:
        legacy = project_config_service.read_project_config()
        legacy_value = legacy.get("web_ui_token_expire_days")
        if legacy_value is not None:
            config["token_expire_days"] = legacy_value
    return _validate_config(WebUIConfig, config)
