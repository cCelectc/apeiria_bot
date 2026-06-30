from __future__ import annotations

from nonebot import get_driver


def get_superuser_set() -> set[str]:
    return set(get_driver().config.superusers)
