from __future__ import annotations

from typing import TYPE_CHECKING

from nonebot import require
from nonebot.exception import IgnoredException
from nonebot.matcher import Matcher  # noqa: TC002
from nonebot.message import run_preprocessor

require("nonebot_plugin_uninfo")
from nonebot_plugin_uninfo import Uninfo  # noqa: TC002

if TYPE_CHECKING:
    from nonebot_plugin_uninfo import Session

_installed = False


def resolve_subject(session: Session) -> tuple[str, str | None]:
    user_id = session.user.id
    group_id = session.scene.id if session.scene.is_group else None
    return user_id, group_id


def check_access(plugin_name: str, user_id: str, group_id: str | None) -> bool:
    from apeiria.bootstrap.steps import get_access_control

    return get_access_control().evaluate(user_id, group_id, plugin_name)


async def access_preprocessor(matcher: Matcher, session: Uninfo) -> None:
    user_id, group_id = resolve_subject(session)
    plugin_name = matcher.plugin_name or ""
    if not check_access(plugin_name, user_id, group_id):
        raise IgnoredException("blocked by access control")  # noqa: TRY003


def install_access_hook() -> None:
    global _installed  # noqa: PLW0603
    if _installed:
        return
    run_preprocessor(access_preprocessor)
    _installed = True
