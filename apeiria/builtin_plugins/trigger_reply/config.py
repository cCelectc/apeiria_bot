from __future__ import annotations

from collections.abc import Sequence
from pathlib import PurePath

from pydantic import BaseModel, ConfigDict

from apeiria.config import project_config_service
from apeiria.config.normalizers import normalize_bool, normalize_int, validate_config

DEFAULT_ENABLED = True
DEFAULT_PRIORITY = 12
DEFAULT_STOP_PROPAGATION_ON_MATCH = True
DEFAULT_RULES_FILE = "rules.toml"
DEFAULT_DEBUG = False


class TriggerReplyConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    enabled: bool = DEFAULT_ENABLED
    priority: int = DEFAULT_PRIORITY
    stop_propagation_on_match: bool = DEFAULT_STOP_PROPAGATION_ON_MATCH
    rules_file: tuple[str, ...] = (DEFAULT_RULES_FILE,)
    debug: bool = DEFAULT_DEBUG


def normalize_trigger_reply_config(data: dict[str, object]) -> dict[str, object]:
    return {
        "enabled": normalize_bool(
            data.get("enabled"),
            fallback=DEFAULT_ENABLED,
        ),
        "priority": normalize_int(
            data.get("priority"),
            fallback=DEFAULT_PRIORITY,
            min_value=1,
        ),
        "stop_propagation_on_match": normalize_bool(
            data.get("stop_propagation_on_match"),
            fallback=DEFAULT_STOP_PROPAGATION_ON_MATCH,
        ),
        "rules_file": _normalize_rules_file(
            data.get("rules_file"),
            fallback=DEFAULT_RULES_FILE,
        ),
        "debug": normalize_bool(data.get("debug"), fallback=DEFAULT_DEBUG),
    }


def get_trigger_reply_config() -> TriggerReplyConfig:
    config = normalize_trigger_reply_config(
        project_config_service.read_project_plugin_config("trigger_reply")
    )
    return validate_config(TriggerReplyConfig, config)


def _normalize_rules_file(value: object, *, fallback: str) -> tuple[str, ...]:
    candidates: list[str]
    if isinstance(value, str):
        candidates = [value]
    elif isinstance(value, Sequence):
        candidates = [item for item in value if isinstance(item, str)]
    else:
        candidates = []
    paths = tuple(
        text
        for item in candidates
        if (text := _normalize_rules_file_item(item)) is not None
    )
    return paths or (fallback,)


def _normalize_rules_file_item(value: str) -> str | None:
    text = value.strip()
    if not text or PurePath(text).is_absolute() or ".." in PurePath(text).parts:
        return None
    return text


__all__ = [
    "DEFAULT_DEBUG",
    "DEFAULT_ENABLED",
    "DEFAULT_PRIORITY",
    "DEFAULT_RULES_FILE",
    "DEFAULT_STOP_PROPAGATION_ON_MATCH",
    "TriggerReplyConfig",
    "get_trigger_reply_config",
    "normalize_trigger_reply_config",
]
