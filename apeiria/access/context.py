"""Access context helpers for runtime events."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nonebot import get_driver

from apeiria.access.level import (
    group_id_from_event,
    resolve_conversation_type,
)
from apeiria.access.models import AccessContext

if TYPE_CHECKING:
    from nonebot.adapters import Bot, Event


async def build_access_context(_bot: Bot, event: Event) -> AccessContext | None:
    """Build one normalized access context from a runtime event."""
    try:
        user_id = event.get_user_id()
    except Exception:  # noqa: BLE001
        return None

    group_id = group_id_from_event(event)
    conversation_type = resolve_conversation_type(event, user_id, group_id)

    superusers = {
        str(item) for item in getattr(get_driver().config, "superusers", set())
    }
    return AccessContext(
        user_id=user_id,
        group_id=group_id,
        conversation_type=conversation_type,
        is_superuser=str(user_id) in superusers,
    )
