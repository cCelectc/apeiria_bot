import base64
from typing import Any, cast

from nonebot.adapters import Bot, Event
from nonebot.log import logger
from nonebot_plugin_alconna.uniseg.builder import MessageBuilder, build
from nonebot_plugin_alconna.uniseg.constraint import SupportAdapter
from nonebot_plugin_alconna.uniseg.exporter import MessageExporter, Target, export
from nonebot_plugin_alconna.uniseg.segment import Image, Text

from apeiria.webchat.message import Message, MessageSegment


class WebChatExporter(MessageExporter[Message]):
    """把 UniMessage 导出为 WebChat Message（text/image），并经 bot.send 发送。"""

    def get_message_type(self) -> type[Message]:
        return Message

    @classmethod
    def get_adapter(cls) -> SupportAdapter:
        return cast("SupportAdapter", "WebChat")

    def get_message_id(self, event: Event) -> str:
        return getattr(event, "message_id", "")

    @export
    async def text(self, seg: Text, bot: Bot | None) -> MessageSegment:  # noqa: ARG002
        return MessageSegment.text(seg.text)

    @export
    async def image(self, seg: Image, bot: Bot | None) -> MessageSegment:  # noqa: ARG002
        if seg.url:
            return MessageSegment.image(url=seg.url)
        try:
            raw = seg.raw_bytes
        except (ValueError, OSError):
            return MessageSegment.raw("image", {"name": seg.name, "id": seg.id})
        mime = seg.mimetype or "image/png"
        encoded = base64.b64encode(raw).decode()
        return MessageSegment.image(base64=f"data:{mime};base64,{encoded}")

    async def send_to(  # pyright: ignore[reportIncompatibleMethodOverride]
        self,
        target: Target | Event,
        bot: Bot,
        message: Message,
        **kwargs: Any,
    ) -> Any:
        if isinstance(target, Event):
            return await bot.send(target, message, **kwargs)
        logger.warning("WebChat: proactive send_to without event is unsupported")
        return None


class WebChatBuilder(MessageBuilder):
    """把 WebChat 原生消息构建为 UniMessage（text 由基类默认处理，这里补 image）。"""

    @classmethod
    def get_adapter(cls) -> SupportAdapter:
        return cast("SupportAdapter", "WebChat")

    @build("image")
    def image(self, seg: MessageSegment) -> Image:
        return Image(url=seg.data.get("url") or seg.data.get("base64") or None)


def register_alconna() -> None:
    from nonebot_plugin_alconna.uniseg.adapters import (
        BUILDER_MAPPING,
        EXPORTER_MAPPING,
    )

    EXPORTER_MAPPING["WebChat"] = WebChatExporter()
    BUILDER_MAPPING["WebChat"] = WebChatBuilder()
    logger.success("WebChat alconna exporter/builder registered")
