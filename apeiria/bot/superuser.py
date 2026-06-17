"""Centralized superuser identity checks for bot-surface access control."""

from __future__ import annotations

from functools import lru_cache

from nonebot import get_driver


@lru_cache(maxsize=1)
def get_superuser_set() -> set[str]:
    """Return the configured superuser id set, normalised to strings."""
    superusers = getattr(get_driver().config, "superusers", set())
    return {str(item) for item in superusers}


def is_superuser_id(user_id: str, *, adapter_prefix: str = "") -> bool:
    """Check whether *user_id* is a configured superuser.

    When *adapter_prefix* is provided, ``{adapter_prefix}:{user_id}`` is
    also checked (e.g. ``onebot:12345``).
    """
    candidates = {user_id}
    if adapter_prefix:
        candidates.add(f"{adapter_prefix}:{user_id}")
    return bool(candidates & get_superuser_set())
