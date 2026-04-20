"""Session identity inspection command."""

from __future__ import annotations

from arclet.alconna import CommandMeta
from nonebot.adapters import Bot, Event  # noqa: TC002
from nonebot_plugin_alconna import Alconna, on_alconna

from apeiria.i18n import t

from .presenter import render_block
from .utils import ensure_owner_message

_session = on_alconna(
    Alconna("sid", meta=CommandMeta(description=t("admin.command.sid"))),
    use_cmd_start=True,
    priority=5,
    block=True,
)


@_session.handle()
async def handle_session(bot: Bot, event: Event) -> None:
    owner_error = ensure_owner_message(event)
    if owner_error:
        await _session.finish(owner_error)

    session_id = _safe_get_session_id(event) or ""
    user_id = _safe_get_user_id(event) or ""
    message_type = _resolve_message_type(event)
    source_id = f"{bot.self_id}:{message_type}:{session_id}"
    await _session.finish(
        render_block(
            t("admin.session.title"),
            [
                (t("admin.session.field_bot"), bot.self_id),
                (t("admin.session.field_user"), user_id),
                (t("admin.session.field_session"), session_id),
                (t("admin.session.field_type"), message_type),
                ("SID", source_id),
            ],
            summary=t("admin.session.summary"),
        )
    )


def _safe_get_user_id(event: Event) -> str | None:
    try:
        return event.get_user_id()
    except Exception:  # noqa: BLE001
        return None


def _safe_get_session_id(event: Event) -> str | None:
    try:
        return event.get_session_id()
    except Exception:  # noqa: BLE001
        return None


def _resolve_message_type(event: Event) -> str:
    message_type = getattr(event, "message_type", None)
    if isinstance(message_type, str) and message_type.strip():
        return message_type.strip()
    return event.__class__.__name__
