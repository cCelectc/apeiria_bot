from __future__ import annotations

"""Configuration model for the shared render plugin."""

from typing import TypeVar

from pydantic import BaseModel, Field

from apeiria.config import project_config_service

ModelT = TypeVar("ModelT", bound=BaseModel)


class RenderConfig(BaseModel):
    headless: bool = True
    channel: str = ""
    executable_path: str = ""
    launch_args: list[str] = Field(default_factory=list)
    browser_locale: str = "zh-CN"
    user_agent: str = ""
    default_width: int = 960
    default_height: int = 540
    default_device_scale_factor: float = 2.0
    default_timeout_ms: int = 15_000
    max_concurrency: int = 2
    startup_warmup: bool = True


def _validate_config(model: type[ModelT], data: dict[str, object]) -> ModelT:
    return model.model_validate(data)


def _coerce_positive_int(value: object, fallback: int) -> int:
    if isinstance(value, bool):
        return fallback
    if not isinstance(value, (int, float, str)):
        return fallback
    try:
        return max(int(value), 1)
    except (TypeError, ValueError):
        return fallback


def _coerce_min_float(value: object, fallback: float, minimum: float) -> float:
    if isinstance(value, bool):
        return fallback
    if not isinstance(value, (int, float, str)):
        return fallback
    try:
        return max(float(value), minimum)
    except (TypeError, ValueError):
        return fallback


def _normalize_render_config(data: dict[str, object]) -> dict[str, object]:
    """Normalize raw plugin config to a safe runtime shape."""
    normalized = dict(data)

    for key in ("channel", "executable_path", "user_agent"):
        value = normalized.get(key, "")
        normalized[key] = value.strip() if isinstance(value, str) else ""

    locale = normalized.get("browser_locale", "zh-CN")
    if isinstance(locale, str) and locale.strip():
        normalized["browser_locale"] = locale.strip()
    else:
        normalized["browser_locale"] = "zh-CN"

    raw_launch_args = normalized.get("launch_args", [])
    if isinstance(raw_launch_args, list):
        normalized["launch_args"] = [
            item.strip()
            for item in raw_launch_args
            if isinstance(item, str) and item.strip()
        ]
    else:
        normalized["launch_args"] = []

    for key, fallback in (
        ("default_width", 960),
        ("default_height", 540),
        ("default_timeout_ms", 15_000),
        ("max_concurrency", 2),
    ):
        normalized[key] = _coerce_positive_int(normalized.get(key, fallback), fallback)

    normalized["default_device_scale_factor"] = _coerce_min_float(
        normalized.get("default_device_scale_factor", 2.0),
        2.0,
        1.0,
    )

    return normalized


def get_render_config() -> RenderConfig:
    config = _normalize_render_config(
        project_config_service.read_project_plugin_config("render")
    )
    return _validate_config(RenderConfig, config)
