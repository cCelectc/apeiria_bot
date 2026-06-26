from __future__ import annotations

from apeiria.config.loader import load_config


def get_superuser_set() -> set[str]:
    app = load_config("data/config.yaml")
    return set(app.nonebot.superusers)


def is_superuser_id(user_id: str) -> bool:
    return user_id in get_superuser_set()
