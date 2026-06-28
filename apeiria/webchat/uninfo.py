from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from nonebot.adapters import Bot  # noqa: TC002
from nonebot.log import logger
from nonebot_plugin_uninfo.fetch import InfoFetcher as BaseInfoFetcher
from nonebot_plugin_uninfo.model import Member, Scene, SceneType, User

from apeiria.webchat.event import WebChatMessageEvent  # noqa: TC001

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from nonebot_plugin_uninfo.constraint import SupportAdapter, SupportScope
    from nonebot_plugin_uninfo.model import BasicInfo


class WebChatInfoFetcher(BaseInfoFetcher):
    """把 WebChat 事件解析为 uninfo Session（单用户；私聊/群聊场景）。"""

    def extract_user(self, data: dict[str, Any]) -> User:
        return User(id=data["user_id"], name=data.get("name"))

    def extract_scene(self, data: dict[str, Any]) -> Scene:
        is_group = data.get("scene_type") == "group"
        return Scene(
            id=data["scene_id"],
            type=SceneType.GROUP if is_group else SceneType.PRIVATE,
            name=data.get("scene_id"),
        )

    def extract_member(self, data: dict[str, Any], user: User | None) -> Member | None:
        if data.get("scene_type") != "group":
            return None
        if user is None:
            user = self.extract_user(data)
        return Member(user, nick=user.name)

    def supply_self(self, bot: Bot) -> BasicInfo:
        return {
            "self_id": str(bot.self_id),
            "adapter": cast("SupportAdapter", "WebChat"),
            "scope": cast("SupportScope", "WebChat"),
        }

    async def query_user(self, bot: Bot, user_id: str) -> User | None:  # noqa: ARG002
        return User(id=user_id)

    async def query_scene(
        self,
        bot: Bot,  # noqa: ARG002
        scene_type: SceneType,
        scene_id: str,
        *,
        parent_scene_id: str | None = None,  # noqa: ARG002
    ) -> Scene | None:
        return Scene(id=scene_id, type=scene_type)

    async def query_member(
        self,
        bot: Bot,  # noqa: ARG002
        scene_type: SceneType,  # noqa: ARG002
        parent_scene_id: str,  # noqa: ARG002
        user_id: str,  # noqa: ARG002
    ) -> Member | None:
        return None

    async def query_users(self, bot: Bot) -> AsyncGenerator[User, None]:  # noqa: ARG002
        for item in ():
            yield item

    async def query_scenes(
        self,
        bot: Bot,  # noqa: ARG002
        scene_type: SceneType | None = None,  # noqa: ARG002
        *,
        parent_scene_id: str | None = None,  # noqa: ARG002
    ) -> AsyncGenerator[Scene, None]:
        for item in ():
            yield item

    async def query_members(
        self,
        bot: Bot,  # noqa: ARG002
        scene_type: SceneType,  # noqa: ARG002
        parent_scene_id: str,  # noqa: ARG002
    ) -> AsyncGenerator[Member, None]:
        for item in ():
            yield item


fetcher = WebChatInfoFetcher(cast("SupportAdapter", "WebChat"))


@fetcher.supply
async def _supply_message(bot: Bot, event: WebChatMessageEvent) -> dict:  # noqa: ARG001
    return {
        "user_id": event.user_id,
        "name": event.user_id,
        "scene_type": event.scene_type,
        "scene_id": event.scene_id,
    }


def register_uninfo() -> None:
    from nonebot_plugin_uninfo.adapters import INFO_FETCHER_MAPPING

    INFO_FETCHER_MAPPING["WebChat"] = fetcher
    logger.success("WebChat uninfo fetcher registered")
