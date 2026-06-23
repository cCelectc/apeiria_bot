from __future__ import annotations

"""Configuration model for the Web UI plugin."""

from typing import TypeVar

from pydantic import BaseModel

from .project import project_config_service

ModelT = TypeVar("ModelT", bound=BaseModel)


class WebUIConfig(BaseModel):
    """Runtime configuration for the Web UI plugin."""

    session_ttl_days: int = 7


def _validate_config(model: type[ModelT], data: dict[str, object]) -> ModelT:
    """Validate plugin config data against a Pydantic model."""
    return model.model_validate(data)


def get_web_ui_config() -> WebUIConfig:
    """Read Web UI config from the canonical plugin config section."""
    config = project_config_service.read_project_plugin_config("web_ui")
    return _validate_config(WebUIConfig, config)
