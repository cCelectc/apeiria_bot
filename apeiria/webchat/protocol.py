from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apeiria.webchat.message import Message, MessageSegment


class ProtocolError(ValueError):
    """入站帧不合法。"""


@dataclass
class InboundMessage:
    text: str
    image: str | None
    identity: dict[str, Any]


@dataclass
class InboundClear:
    pass


@dataclass
class InboundDelete:
    message_id: str


@dataclass
class InboundSwitch:
    identity: dict[str, Any]


InboundFrame = InboundMessage | InboundClear | InboundDelete | InboundSwitch


def parse_inbound(raw: Any) -> InboundFrame:
    if not isinstance(raw, dict):
        raise ProtocolError("frame must be an object")  # noqa: TRY003
    ftype = raw.get("type")
    if ftype == "message":
        text = str(raw.get("text") or "")
        image = raw.get("image")
        identity = raw.get("identity") or {}
        if not isinstance(identity, dict):
            raise ProtocolError("identity must be an object")  # noqa: TRY003
        if not text and not image:
            raise ProtocolError("message requires text or image")  # noqa: TRY003
        return InboundMessage(text=text, image=image, identity=identity)
    if ftype == "clear":
        return InboundClear()
    if ftype == "delete":
        message_id = raw.get("message_id")
        if message_id is None or message_id == "":
            raise ProtocolError("delete requires message_id")  # noqa: TRY003
        return InboundDelete(message_id=str(message_id))
    if ftype == "switch":
        identity = raw.get("identity") or {}
        if not isinstance(identity, dict):
            raise ProtocolError("identity must be an object")  # noqa: TRY003
        return InboundSwitch(identity=identity)
    raise ProtocolError(f"unknown frame type: {ftype!r}")  # noqa: TRY003


def build_inbound_message(text: str, image: str | None) -> Message:
    """把入站文本/图片组装成 WebChat Message。"""
    msg = Message()
    if text:
        msg.append(MessageSegment.text(text))
    if image:
        if image.startswith(("http://", "https://")):
            msg.append(MessageSegment.image(url=image))
        else:
            msg.append(MessageSegment.image(base64=image))
    if not msg:
        msg.append(MessageSegment.text(""))
    return msg


def message_to_wire(message: Message) -> list[dict[str, Any]]:
    """把出站 Message 逐段序列化为 wire 段；未知段降级为 raw 调试段。"""
    wire: list[dict[str, Any]] = []
    for seg in message:
        if seg.type == "text":
            wire.append({"type": "text", "text": seg.data.get("text", "")})
        elif seg.type == "image":
            url = seg.data.get("url") or seg.data.get("base64") or ""
            wire.append({"type": "image", "url": url})
        elif seg.type == "raw":
            wire.append(
                {
                    "type": "raw",
                    "seg_type": seg.data.get("seg_type", "raw"),
                    "data": seg.data.get("data", {}),
                }
            )
        else:
            wire.append({"type": "raw", "seg_type": seg.type, "data": dict(seg.data)})
    return wire


def wire_message(  # noqa: PLR0913
    *,
    message_id: str,
    role: str,
    segments: list[dict[str, Any]],
    time: str,
    session_id: str,
    user_id: str | None = None,
) -> dict[str, Any]:
    return {
        "id": message_id,
        "role": role,
        "segments": segments,
        "time": time,
        "session_id": session_id,
        "user_id": user_id,
    }


def message_frame(wire_msg: dict[str, Any]) -> dict[str, Any]:
    return {"type": "message", "message": wire_msg}


def history_frame(messages: list[dict[str, Any]], session_id: str) -> dict[str, Any]:
    return {"type": "history", "session_id": session_id, "messages": messages}


def cleared_frame(session_id: str) -> dict[str, Any]:
    return {"type": "cleared", "session_id": session_id}


def deleted_frame(message_id: str) -> dict[str, Any]:
    return {"type": "deleted", "message_id": message_id}


def error_frame(code: str, message: str) -> dict[str, Any]:
    return {"type": "error", "code": code, "message": message}
