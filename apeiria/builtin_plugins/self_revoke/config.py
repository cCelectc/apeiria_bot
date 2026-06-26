from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from apeiria.config import project_config_service
from apeiria.config.normalizers import normalize_bool, normalize_choice, validate_config

SelfRevokePermission = Literal["public", "superuser"]
SelfRevokeFeedback = Literal["silent", "reaction"]

_PERMISSION_VALUES = {"public", "superuser"}
_FEEDBACK_VALUES = {"silent", "reaction"}


class SelfRevokeConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    permission: SelfRevokePermission = "public"
    revoke_trigger_message: bool = False
    feedback: SelfRevokeFeedback = "silent"


def normalize_self_revoke_config(data: dict[str, object]) -> dict[str, object]:
    """Normalize raw project config into a safe self-revoke config payload."""

    return {
        "permission": normalize_choice(
            data.get("permission", "public"),
            allowed=_PERMISSION_VALUES,
            fallback="public",
        ),
        "revoke_trigger_message": normalize_bool(
            data.get("revoke_trigger_message", False),
            fallback=False,
        ),
        "feedback": normalize_choice(
            data.get("feedback", "silent"),
            allowed=_FEEDBACK_VALUES,
            fallback="silent",
        ),
    }


def get_self_revoke_config() -> SelfRevokeConfig:
    config = normalize_self_revoke_config(
        project_config_service.read_project_plugin_config("self_revoke")
    )
    return validate_config(SelfRevokeConfig, config)


__all__ = [
    "SelfRevokeConfig",
    "SelfRevokeFeedback",
    "SelfRevokePermission",
    "get_self_revoke_config",
    "normalize_self_revoke_config",
]
