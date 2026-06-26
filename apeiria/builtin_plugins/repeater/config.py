from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Literal

from pydantic import BaseModel, ConfigDict

from apeiria.config import project_config_service
from apeiria.config.normalizers import (
    iter_raw_values,
    normalize_bool,
    normalize_float,
    normalize_int,
)

GroupMode = Literal["allowlist", "blocklist"]

DEFAULT_REPEAT_THRESHOLD = 2
DEFAULT_PLATFORMS = ("qq",)
DEFAULT_GROUP_MODE: GroupMode = "allowlist"
DEFAULT_BASE_PROBABILITY = 0.25
DEFAULT_MAX_PROBABILITY = 0.9
DEFAULT_SATURATION_EXTRA = 4


class RepeaterConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    repeat_threshold: int = DEFAULT_REPEAT_THRESHOLD
    platforms: tuple[str, ...] = DEFAULT_PLATFORMS
    group_mode: str = DEFAULT_GROUP_MODE
    allow_groups: frozenset[str] = frozenset()
    deny_groups: frozenset[str] = frozenset()
    base_probability: float = DEFAULT_BASE_PROBABILITY
    max_probability: float = DEFAULT_MAX_PROBABILITY
    saturation_extra: int = DEFAULT_SATURATION_EXTRA
    debug: bool = False
    active: bool = True
    errors: tuple[str, ...] = ()
    ignored_group_entries: tuple[str, ...] = ()

    def is_group_allowed(self, group_scope: str) -> bool:
        """Return whether a normalized ``platform:group_id`` scope is enabled."""

        if group_scope in self.deny_groups:
            return False
        if self.group_mode == "allowlist":
            return group_scope in self.allow_groups
        return True


@dataclass(frozen=True, slots=True)
class GroupEntryNormalization:
    valid: frozenset[str]
    ignored: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _ValidationInput:
    repeat_threshold: int
    platforms: tuple[str, ...]
    group_mode: str
    base_probability: float
    max_probability: float
    saturation_extra: int


def normalize_repeater_config(data: dict[str, object]) -> dict[str, object]:
    """Normalize raw project config into a bounded repeater payload."""

    repeat_threshold = normalize_int(
        data.get("repeat_threshold"),
        fallback=DEFAULT_REPEAT_THRESHOLD,
    )
    platforms = _normalize_string_tuple(
        data.get("platforms"),
        fallback=DEFAULT_PLATFORMS,
        lower=True,
    )
    group_mode = _normalize_group_mode(data.get("group_mode"))
    base_probability = normalize_float(
        data.get("base_probability"),
        fallback=DEFAULT_BASE_PROBABILITY,
    )
    max_probability = normalize_float(
        data.get("max_probability"),
        fallback=DEFAULT_MAX_PROBABILITY,
    )
    saturation_extra = normalize_int(
        data.get("saturation_extra"),
        fallback=DEFAULT_SATURATION_EXTRA,
    )
    debug = normalize_bool(data.get("debug"), fallback=False)

    allow_groups = normalize_group_entries(
        data.get("allow_groups"),
        platforms=platforms,
    )
    deny_groups = normalize_group_entries(
        data.get("deny_groups"),
        platforms=platforms,
    )
    errors = _config_errors(
        _ValidationInput(
            repeat_threshold=repeat_threshold,
            platforms=platforms,
            group_mode=group_mode,
            base_probability=base_probability,
            max_probability=max_probability,
            saturation_extra=saturation_extra,
        )
    )

    return {
        "repeat_threshold": repeat_threshold,
        "platforms": platforms,
        "group_mode": group_mode,
        "allow_groups": allow_groups.valid,
        "deny_groups": deny_groups.valid,
        "base_probability": base_probability,
        "max_probability": max_probability,
        "saturation_extra": saturation_extra,
        "debug": debug,
        "active": not errors,
        "errors": errors,
        "ignored_group_entries": allow_groups.ignored + deny_groups.ignored,
    }


def normalize_group_entries(
    values: object,
    *,
    platforms: tuple[str, ...],
) -> GroupEntryNormalization:
    """Normalize ``platform:group_id`` strings and collect ignored entries."""

    valid: set[str] = set()
    ignored: list[str] = []
    enabled_platforms = set(platforms)

    for item in _iter_string_values(values):
        platform, separator, group_id = item.partition(":")
        normalized_platform = platform.strip().lower()
        normalized_group_id = group_id.strip()
        if (
            separator != ":"
            or not normalized_platform
            or not normalized_group_id
            or normalized_platform not in enabled_platforms
        ):
            ignored.append(item)
            continue
        valid.add(f"{normalized_platform}:{normalized_group_id}")

    return GroupEntryNormalization(valid=frozenset(valid), ignored=tuple(ignored))


def get_repeater_config() -> RepeaterConfig:
    config = normalize_repeater_config(
        project_config_service.read_project_plugin_config("repeater")
    )
    return RepeaterConfig.model_validate(config)


def _config_errors(values: _ValidationInput) -> tuple[str, ...]:
    errors: list[str] = []
    if values.repeat_threshold < DEFAULT_REPEAT_THRESHOLD:
        errors.append("repeat_threshold must be >= 2")
    if not values.platforms:
        errors.append("platforms must not be empty")
    if values.group_mode not in {"allowlist", "blocklist"}:
        errors.append("group_mode must be allowlist or blocklist")
    if not isfinite(values.base_probability):
        errors.append("base_probability must be finite")
    elif values.base_probability < 0:
        errors.append("base_probability must be >= 0")
    if not isfinite(values.max_probability):
        errors.append("max_probability must be finite")
    elif values.max_probability > 1:
        errors.append("max_probability must be <= 1")
    if (
        isfinite(values.base_probability)
        and isfinite(values.max_probability)
        and values.base_probability > values.max_probability
    ):
        errors.append("base_probability must be <= max_probability")
    if values.saturation_extra < 1:
        errors.append("saturation_extra must be >= 1")
    return tuple(errors)


def _normalize_group_mode(value: object) -> str:
    if not isinstance(value, str):
        return DEFAULT_GROUP_MODE
    normalized = value.strip().lower()
    return normalized or DEFAULT_GROUP_MODE


def _normalize_string_tuple(
    value: object,
    *,
    fallback: tuple[str, ...],
    lower: bool = False,
    keep_empty: bool = False,
) -> tuple[str, ...]:
    values = tuple(
        item.lower() if lower else item
        for item in (_normalize_text(raw) for raw in iter_raw_values(value))
        if item is not None and (keep_empty or item)
    )
    return values if value is not None else fallback


def _iter_string_values(value: object) -> tuple[str, ...]:
    return tuple(
        item
        for item in (_normalize_text(raw) for raw in iter_raw_values(value))
        if item
    )


def _normalize_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    return value.strip()


__all__ = [
    "DEFAULT_BASE_PROBABILITY",
    "DEFAULT_GROUP_MODE",
    "DEFAULT_MAX_PROBABILITY",
    "DEFAULT_PLATFORMS",
    "DEFAULT_REPEAT_THRESHOLD",
    "DEFAULT_SATURATION_EXTRA",
    "GroupMode",
    "RepeaterConfig",
    "get_repeater_config",
    "normalize_group_entries",
    "normalize_repeater_config",
]
