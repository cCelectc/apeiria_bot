"""Permission checking utilities."""

from __future__ import annotations

from apeiria.access.level import extract_group_id as _extract_group_id
from apeiria.access.service import access_service
from apeiria.plugins.policy import plugin_policy_service
from apeiria.plugins.protection import get_default_protection_mode


def extract_group_id(session_id: str, user_id: str) -> str | None:
    """Extract group_id from a NoneBot session id."""
    return _extract_group_id(session_id, user_id)


async def get_user_level(user_id: str, group_id: str) -> int:
    """Get a user's permission level in a group."""
    return await access_service.get_user_level(user_id, group_id)


async def check_permission(user_id: str, group_id: str, required_level: int) -> bool:
    """Check if user meets the required permission level."""
    return await get_user_level(user_id, group_id) >= required_level


async def is_plugin_enabled(group_id: str, plugin_module: str) -> bool:
    """Check if a plugin is enabled in a group."""
    if get_default_protection_mode(plugin_module) == "required":
        return True
    return await access_service.is_group_plugin_enabled(group_id, plugin_module)


async def is_group_bot_enabled(group_id: str) -> bool:
    """Check whether the bot is enabled for a group."""
    return await access_service.is_group_bot_enabled(group_id)


async def is_plugin_globally_enabled(plugin_module: str) -> bool:
    """Check if a plugin is globally enabled."""
    return await plugin_policy_service.is_globally_enabled(plugin_module)


async def set_user_level(user_id: str, group_id: str, level: int) -> None:
    """Set user's permission level in a group. Invalidates cache."""
    await access_service.set_user_level(user_id, group_id, level)
