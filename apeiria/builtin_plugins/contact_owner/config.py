from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from apeiria.config import project_config_service
from apeiria.config.normalizers import (
    normalize_int,
    normalize_non_empty_string,
    normalize_string,
    validate_config,
)

DEFAULT_CONTACT_PREFIX = "联系主人"
DEFAULT_SUCCESS_REPLY = "已给主人留言。"
DEFAULT_EMPTY_MESSAGE_REPLY = "请在前缀后写下要留言的内容。"
DEFAULT_TOO_SHORT_REPLY = "留言太短，请补充后再发送。"
DEFAULT_OWNER_UNCONFIGURED_REPLY = "主人联系方式未配置，暂时无法留言。"
DEFAULT_INVALID_OWNER_TARGET_REPLY = "主人联系方式配置有误，暂时无法留言。"
DEFAULT_UNSUPPORTED_PLATFORM_REPLY = "当前平台暂不支持联系主人。"
DEFAULT_DELIVERY_FAILED_REPLY = "留言发送失败，请稍后再试。"


class ContactOwnerConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    contact_prefix: str = DEFAULT_CONTACT_PREFIX
    owner_target: str = ""
    minimum_message_length: int = 0
    success_reply: str = DEFAULT_SUCCESS_REPLY
    empty_message_reply: str = DEFAULT_EMPTY_MESSAGE_REPLY
    too_short_reply: str = DEFAULT_TOO_SHORT_REPLY
    owner_unconfigured_reply: str = DEFAULT_OWNER_UNCONFIGURED_REPLY
    invalid_owner_target_reply: str = DEFAULT_INVALID_OWNER_TARGET_REPLY
    unsupported_platform_reply: str = DEFAULT_UNSUPPORTED_PLATFORM_REPLY
    delivery_failed_reply: str = DEFAULT_DELIVERY_FAILED_REPLY


def normalize_contact_owner_config(data: dict[str, object]) -> dict[str, object]:
    """Normalize raw project config into a bounded contact-owner config."""

    return {
        "contact_prefix": normalize_non_empty_string(
            data.get("contact_prefix"),
            fallback=DEFAULT_CONTACT_PREFIX,
        ),
        "owner_target": normalize_string(data.get("owner_target"), fallback=""),
        "minimum_message_length": normalize_int(
            data.get("minimum_message_length"),
            fallback=0,
            min_value=0,
        ),
        "success_reply": normalize_non_empty_string(
            data.get("success_reply"),
            fallback=DEFAULT_SUCCESS_REPLY,
        ),
        "empty_message_reply": normalize_non_empty_string(
            data.get("empty_message_reply"),
            fallback=DEFAULT_EMPTY_MESSAGE_REPLY,
        ),
        "too_short_reply": normalize_non_empty_string(
            data.get("too_short_reply"),
            fallback=DEFAULT_TOO_SHORT_REPLY,
        ),
        "owner_unconfigured_reply": normalize_non_empty_string(
            data.get("owner_unconfigured_reply"),
            fallback=DEFAULT_OWNER_UNCONFIGURED_REPLY,
        ),
        "invalid_owner_target_reply": normalize_non_empty_string(
            data.get("invalid_owner_target_reply"),
            fallback=DEFAULT_INVALID_OWNER_TARGET_REPLY,
        ),
        "unsupported_platform_reply": normalize_non_empty_string(
            data.get("unsupported_platform_reply"),
            fallback=DEFAULT_UNSUPPORTED_PLATFORM_REPLY,
        ),
        "delivery_failed_reply": normalize_non_empty_string(
            data.get("delivery_failed_reply"),
            fallback=DEFAULT_DELIVERY_FAILED_REPLY,
        ),
    }


def get_contact_owner_config() -> ContactOwnerConfig:
    config = normalize_contact_owner_config(
        project_config_service.read_project_plugin_config("contact_owner")
    )
    return validate_config(ContactOwnerConfig, config)


__all__ = [
    "ContactOwnerConfig",
    "get_contact_owner_config",
    "normalize_contact_owner_config",
]
