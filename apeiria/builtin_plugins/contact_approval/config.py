from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from apeiria.config import project_config_service
from apeiria.config.normalizers import (
    normalize_bool,
    normalize_choice,
    normalize_int,
    normalize_non_empty_string,
    normalize_string,
    validate_config,
)

OwnerTargetScope = Literal["qq"]
GroupJoinGateMode = Literal["whitelist", "blacklist"]
SuppressedGroupJoinAction = Literal["ignore", "reject"]

DEFAULT_TICKET_EXPIRATION_MINUTES = 720
DEFAULT_APPROVAL_PREFIX = "审批"
DEFAULT_MISSING_TARGET_REPLY = "请引用审批消息，或带上审批编号，如「同意 #编号」。"
DEFAULT_TICKET_NOT_FOUND_REPLY = "没有找到这个审批。"
DEFAULT_UNAUTHORIZED_REPLY = "你没有处理这个审批的权限。"
DEFAULT_PLATFORM_FAILED_REPLY = (
    "平台操作失败，可能是请求已过期或机器人权限不足。请检查权限或让对方重新申请。"
)

_GATE_MODE_VALUES = {"whitelist", "blacklist"}
_SUPPRESSED_ACTION_VALUES = {"ignore", "reject"}


class OwnerTarget(BaseModel):
    model_config = ConfigDict(extra="ignore")

    scope: OwnerTargetScope
    target_id: str

    @property
    def value(self) -> str:
        return f"{self.scope}:{self.target_id}"


class ContactApprovalConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    owner_targets: tuple[OwnerTarget, ...] = ()
    friend_requests_enabled: bool = True
    bot_group_invites_enabled: bool = True
    group_join_requests_enabled: bool = True
    group_join_gate_mode: GroupJoinGateMode = "whitelist"
    group_join_gate_ids: tuple[str, ...] = ()
    suppressed_group_join_action: SuppressedGroupJoinAction = "ignore"
    suppressed_group_join_reject_reason: str = ""
    ticket_expiration_minutes: int = DEFAULT_TICKET_EXPIRATION_MINUTES
    approval_prefix: str = DEFAULT_APPROVAL_PREFIX
    missing_target_reply: str = DEFAULT_MISSING_TARGET_REPLY
    ticket_not_found_reply: str = DEFAULT_TICKET_NOT_FOUND_REPLY
    unauthorized_reply: str = DEFAULT_UNAUTHORIZED_REPLY
    platform_failed_reply: str = DEFAULT_PLATFORM_FAILED_REPLY


def normalize_contact_approval_config(data: dict[str, object]) -> dict[str, object]:
    """Normalize raw project config into a safe contact-approval config."""

    return {
        "owner_targets": tuple(_normalize_owner_targets(data.get("owner_targets"))),
        "friend_requests_enabled": normalize_bool(
            data.get("friend_requests_enabled", True),
            fallback=True,
        ),
        "bot_group_invites_enabled": normalize_bool(
            data.get("bot_group_invites_enabled", True),
            fallback=True,
        ),
        "group_join_requests_enabled": normalize_bool(
            data.get("group_join_requests_enabled", True),
            fallback=True,
        ),
        "group_join_gate_mode": normalize_choice(
            data.get("group_join_gate_mode", "whitelist"),
            allowed=_GATE_MODE_VALUES,
            fallback="whitelist",
        ),
        "group_join_gate_ids": tuple(
            _normalize_id_list(data.get("group_join_gate_ids"))
        ),
        "suppressed_group_join_action": normalize_choice(
            data.get("suppressed_group_join_action", "ignore"),
            allowed=_SUPPRESSED_ACTION_VALUES,
            fallback="ignore",
        ),
        "suppressed_group_join_reject_reason": normalize_string(
            data.get("suppressed_group_join_reject_reason"),
            fallback="",
        ),
        "ticket_expiration_minutes": normalize_int(
            data.get("ticket_expiration_minutes"),
            fallback=DEFAULT_TICKET_EXPIRATION_MINUTES,
            min_value=1,
        ),
        "approval_prefix": normalize_non_empty_string(
            data.get("approval_prefix"),
            fallback=DEFAULT_APPROVAL_PREFIX,
        ),
        "missing_target_reply": normalize_non_empty_string(
            data.get("missing_target_reply"),
            fallback=DEFAULT_MISSING_TARGET_REPLY,
        ),
        "ticket_not_found_reply": normalize_non_empty_string(
            data.get("ticket_not_found_reply"),
            fallback=DEFAULT_TICKET_NOT_FOUND_REPLY,
        ),
        "unauthorized_reply": normalize_non_empty_string(
            data.get("unauthorized_reply"),
            fallback=DEFAULT_UNAUTHORIZED_REPLY,
        ),
        "platform_failed_reply": normalize_non_empty_string(
            data.get("platform_failed_reply"),
            fallback=DEFAULT_PLATFORM_FAILED_REPLY,
        ),
    }


def get_contact_approval_config() -> ContactApprovalConfig:
    config = normalize_contact_approval_config(
        project_config_service.read_project_plugin_config("contact_approval")
    )
    return validate_config(ContactApprovalConfig, config)


def parse_owner_target(value: object) -> OwnerTarget | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if ":" not in text:
        return None
    raw_scope, raw_target_id = text.split(":", maxsplit=1)
    scope = raw_scope.strip().lower()
    target_id = raw_target_id.strip()
    if scope != "qq" or not _valid_numeric_id(target_id):
        return None
    return OwnerTarget(scope="qq", target_id=target_id)


def _normalize_owner_targets(value: object) -> list[OwnerTarget]:
    raw_items: list[object]
    if isinstance(value, str):
        raw_items = [value]
    elif isinstance(value, (list, tuple, set)):
        raw_items = list(value)
    else:
        raw_items = []

    targets: list[OwnerTarget] = []
    seen: set[str] = set()
    for item in raw_items:
        target = parse_owner_target(item)
        if target is None or target.value in seen:
            continue
        seen.add(target.value)
        targets.append(target)
    return targets


def _normalize_id_list(value: object) -> list[str]:
    raw_items: list[object]
    if isinstance(value, str):
        raw_items = [value]
    elif isinstance(value, (list, tuple, set)):
        raw_items = list(value)
    else:
        raw_items = []

    ids: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        text = str(item).strip() if item is not None else ""
        if not _valid_numeric_id(text) or text in seen:
            continue
        seen.add(text)
        ids.append(text)
    return ids


def _valid_numeric_id(value: str) -> bool:
    return value.isdecimal() and value != "0"


__all__ = [
    "DEFAULT_APPROVAL_PREFIX",
    "DEFAULT_MISSING_TARGET_REPLY",
    "DEFAULT_PLATFORM_FAILED_REPLY",
    "DEFAULT_TICKET_EXPIRATION_MINUTES",
    "DEFAULT_TICKET_NOT_FOUND_REPLY",
    "DEFAULT_UNAUTHORIZED_REPLY",
    "ContactApprovalConfig",
    "GroupJoinGateMode",
    "OwnerTarget",
    "SuppressedGroupJoinAction",
    "get_contact_approval_config",
    "normalize_contact_approval_config",
    "parse_owner_target",
]
