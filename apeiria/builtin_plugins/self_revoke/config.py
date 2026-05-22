from __future__ import annotations

from typing import Literal, TypeVar

from pydantic import BaseModel, ConfigDict

from apeiria.config import project_config_service

ModelT = TypeVar("ModelT", bound=BaseModel)
SelfRevokePermission = Literal["public", "superuser"]
SelfRevokeFeedback = Literal["silent", "reaction"]

_PERMISSION_VALUES = {"public", "superuser"}
_FEEDBACK_VALUES = {"silent", "reaction"}


class SelfRevokeConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    permission: SelfRevokePermission = "public"
    revoke_trigger_message: bool = False
    feedback: SelfRevokeFeedback = "silent"


def _validate_config(model: type[ModelT], data: dict[str, object]) -> ModelT:
    return model.model_validate(data)


def _normalize_choice(
    value: object,
    *,
    allowed: set[str],
    fallback: str,
) -> str:
    if not isinstance(value, str):
        return fallback
    normalized = value.strip().lower()
    return normalized if normalized in allowed else fallback


def _normalize_bool(value: object, *, fallback: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    return fallback


def normalize_self_revoke_config(data: dict[str, object]) -> dict[str, object]:
    """Normalize raw project config into a safe self-revoke config payload."""

    return {
        "permission": _normalize_choice(
            data.get("permission", "public"),
            allowed=_PERMISSION_VALUES,
            fallback="public",
        ),
        "revoke_trigger_message": _normalize_bool(
            data.get("revoke_trigger_message", False),
            fallback=False,
        ),
        "feedback": _normalize_choice(
            data.get("feedback", "silent"),
            allowed=_FEEDBACK_VALUES,
            fallback="silent",
        ),
    }


def get_self_revoke_config() -> SelfRevokeConfig:
    config = normalize_self_revoke_config(
        project_config_service.read_project_plugin_config("self_revoke")
    )
    return _validate_config(SelfRevokeConfig, config)


__all__ = [
    "SelfRevokeConfig",
    "SelfRevokeFeedback",
    "SelfRevokePermission",
    "get_self_revoke_config",
    "normalize_self_revoke_config",
]
