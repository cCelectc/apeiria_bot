"""Alconna / UniSeg / Uninfo compatibility for WebChat."""

import base64
from collections.abc import Sequence
from importlib import import_module
from typing import TYPE_CHECKING, Any

from nonebot.adapters import Bot, Event, Message
from nonebot_plugin_alconna.uniseg.builder import MessageBuilder, build
from nonebot_plugin_alconna.uniseg.constraint import SupportAdapter, SupportScope
from nonebot_plugin_alconna.uniseg.exporter import MessageExporter, Target, export
from nonebot_plugin_alconna.uniseg.segment import At, Emoji, Image, Reply, Segment, Text

from .event import WebChatMessageEvent
from .message import WebChatMessage, WebChatMessageSegment


class WebChatMessageBuilder(MessageBuilder[WebChatMessageSegment]):
    @classmethod
    def get_adapter(cls) -> SupportAdapter:
        return SupportAdapter.onebot11

    @build("image")
    def image(self, seg: WebChatMessageSegment) -> Image:
        data = seg.data
        return Image(
            id=data.get("asset_id"),
            url=data.get("url"),
            raw=base64.b64decode(data["base64"]) if data.get("base64") else None,
            mimetype=data.get("mime"),
        )

    @build("mention")
    def mention(self, seg: WebChatMessageSegment) -> At | None:
        data = seg.data
        target = data.get("target")
        if not isinstance(target, str) or not target:
            return None
        mention_type = data.get("mention_type")
        flag = mention_type if mention_type in {"user", "role", "channel"} else "user"
        return At(
            flag=flag,
            target=target,
            display=data.get("display"),
        )

    @build("reply")
    def reply(self, seg: WebChatMessageSegment) -> Reply | None:
        data = seg.data
        message_id = data.get("message_id") or data.get("id")
        if not isinstance(message_id, str) or not message_id:
            return None
        return Reply(message_id)


class WebChatMessageExporter(MessageExporter[WebChatMessage]):
    def get_message_type(self) -> type[WebChatMessage]:
        return WebChatMessage

    @classmethod
    def get_adapter(cls) -> SupportAdapter:
        return SupportAdapter.onebot11

    def get_target(self, event: Event, bot: Bot | None = None) -> Target:
        assert isinstance(event, WebChatMessageEvent)
        return Target(
            event.get_user_id(),
            private=True,
            adapter=self.get_adapter(),
            self_id=bot.self_id if bot else None,
            scope=SupportScope.qq_client,
        )

    def get_message_id(self, event: Event) -> str:
        assert isinstance(event, WebChatMessageEvent)
        return str(event.message_id)

    @export
    async def text(self, seg: Text, _bot: Bot | None) -> WebChatMessageSegment:
        return WebChatMessageSegment.text(seg.text)

    @export
    async def media(self, seg: Image, _bot: Bot | None) -> WebChatMessageSegment:
        if seg.raw:
            return WebChatMessageSegment.image(
                base64_data=base64.b64encode(seg.raw_bytes).decode("ascii"),
                mime=seg.mimetype,
            )
        return WebChatMessageSegment.image(
            url=seg.url,
            asset_id=seg.id,
            mime=seg.mimetype,
        )

    @export
    async def at(self, seg: At, _bot: Bot | None) -> WebChatMessageSegment:
        return WebChatMessageSegment.mention(
            seg.target,
            display=seg.display,
            mention_type=seg.flag,
        )

    @export
    async def reply(self, seg: Reply, _bot: Bot | None) -> WebChatMessageSegment:
        return WebChatMessageSegment.reply(
            seg.id,
            text=str(seg.msg) if seg.msg else None,
        )

    async def send_to(
        self,
        target: Target | Event,
        bot: Bot,
        message: Message,
        **kwargs: Any,
    ) -> Any:
        if TYPE_CHECKING:
            assert hasattr(bot, "send")
        if isinstance(target, Event):
            return await bot.send(target, message, **kwargs)
        raise NotImplementedError(
            "WebChat exporter only supports sends through event contexts"
        )

    async def recall(self, mid: Any, bot: Bot, context: Target | Event) -> None:
        raise NotImplementedError("WebChat exporter does not support message recall")

    async def edit(
        self,
        new: Sequence[Segment],
        mid: Any,
        bot: Bot,
        context: Target | Event,
    ) -> None:
        raise NotImplementedError("WebChat exporter does not support message editing")

    async def reaction(
        self,
        emoji: Emoji,
        mid: Any,
        bot: Bot,
        context: Target | Event,
        delete: bool = False,  # noqa: FBT001, FBT002
    ) -> None:
        raise NotImplementedError("WebChat exporter does not support reactions")


def register_webchat_uniseg() -> None:
    from nonebot_plugin_alconna.uniseg.adapters import BUILDER_MAPPING, EXPORTER_MAPPING

    EXPORTER_MAPPING["WebChat"] = WebChatMessageExporter()
    BUILDER_MAPPING["WebChat"] = WebChatMessageBuilder()


def _build_webchat_uninfo_fetcher() -> Any | None:  # noqa: C901
    try:
        support_scope = import_module("nonebot_plugin_uninfo.constraint").SupportScope
        base_info_fetcher = import_module("nonebot_plugin_uninfo.fetch").InfoFetcher
        model_module = import_module("nonebot_plugin_uninfo.model")
    except ModuleNotFoundError:
        return None
    support_scope_cls = support_scope
    base_info_fetcher_cls = base_info_fetcher
    scene_cls = model_module.Scene
    scene_type_cls = model_module.SceneType
    user_cls = model_module.User

    class WebChatInfoFetcher(base_info_fetcher_cls):
        def extract_user(self, data: dict[str, Any]) -> Any:
            user_id = str(data["user_id"])
            name = data.get("name")
            return user_cls(
                id=user_id,
                name=str(name) if name else user_id,
                nick=str(data.get("nickname") or name or user_id),
                avatar=str(data.get("avatar")) if data.get("avatar") else None,
            )

        def extract_scene(self, data: dict[str, Any]) -> Any:
            scene_id = str(data.get("scene_id") or data["user_id"])
            scene_name = data.get("scene_name") or data.get("name") or scene_id
            return scene_cls(
                id=scene_id,
                type=scene_type_cls.PRIVATE,
                name=str(scene_name),
                avatar=str(data.get("avatar")) if data.get("avatar") else None,
            )

        def extract_member(
            self,
            data: dict[str, Any],  # noqa: ARG002
            user: Any | None,  # noqa: ARG002
        ) -> None:
            return None

        def supply_self(self, bot: Bot) -> dict[str, Any]:
            return {
                "self_id": str(bot.self_id),
                "adapter": "WebChat",
                "scope": support_scope_cls.unknown,
            }

        async def query_user(self, bot: Bot, user_id: str) -> Any | None:  # noqa: ARG002
            return user_cls(id=user_id, name=user_id, nick=user_id)

        async def query_scene(
            self,
            bot: Bot,  # noqa: ARG002
            scene_type: Any,
            scene_id: str,
            *,
            parent_scene_id: str | None = None,  # noqa: ARG002
        ) -> Any | None:
            if scene_type != scene_type_cls.PRIVATE:
                return None
            return scene_cls(id=scene_id, type=scene_type_cls.PRIVATE, name=scene_id)

        async def query_member(
            self,
            bot: Bot,  # noqa: ARG002
            scene_type: Any,  # noqa: ARG002
            parent_scene_id: str,  # noqa: ARG002
            user_id: str,  # noqa: ARG002
        ) -> None:
            return None

        async def query_users(self, bot: Bot):  # noqa: ARG002
            if False:
                yield user_cls(id="")

        async def query_scenes(
            self,
            bot: Bot,  # noqa: ARG002
            scene_type: Any = None,  # noqa: ARG002
            *,
            parent_scene_id: str | None = None,  # noqa: ARG002
        ):
            if False:
                yield scene_cls(id="", type=scene_type_cls.PRIVATE)

        async def query_members(
            self,
            bot: Bot,  # noqa: ARG002
            scene_type: Any,  # noqa: ARG002
            parent_scene_id: str,  # noqa: ARG002
        ):
            if False:
                yield None

    fetcher = WebChatInfoFetcher("WebChat")

    @fetcher.supply_wildcard
    async def _fetch_webchat_session(bot: Bot, event: Event) -> dict[str, Any]:  # noqa: ARG001
        assert isinstance(event, WebChatMessageEvent)
        user_id = event.get_user_id()
        display_name = event.session.created_by.username or user_id
        return {
            "user_id": user_id,
            "name": display_name,
            "nickname": display_name,
            "scene_id": user_id,
            "scene_name": display_name,
        }

    return fetcher


def register_webchat_uninfo() -> None:
    """Register a minimal Uninfo fetcher for the in-process WebChat adapter.

    WebChat is an internal adapter, so upstream `nonebot_plugin_uninfo` does not
    know how to resolve it. A lightweight private-session fetcher is enough to
    stop warning spam and satisfy libraries that probe session metadata.
    """

    try:
        info_fetcher_mapping = import_module("nonebot_plugin_uninfo.adapters")
    except ModuleNotFoundError:
        return

    fetcher = _build_webchat_uninfo_fetcher()
    if fetcher is not None:
        info_fetcher_mapping.INFO_FETCHER_MAPPING["WebChat"] = fetcher
