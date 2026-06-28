from __future__ import annotations

import asyncio
import json
import time
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import nonebot
from nonebot.adapters import Adapter as BaseAdapter
from nonebot.drivers import URL, WebSocket, WebSocketServerSetup
from nonebot.exception import WebSocketClosed
from nonebot.log import logger
from nonebot.message import handle_event

from apeiria.conversation.store import (
    append_message,
    delete_message,
    delete_session_messages,
    ensure_session,
    load_recent,
)
from apeiria.db.base import _now_iso
from apeiria.web.auth import decode_token
from apeiria.webchat import protocol
from apeiria.webchat.bot import WebChatBot
from apeiria.webchat.config import get_webchat_config, resolve_default_user_id
from apeiria.webchat.connection import ConnectionManager
from apeiria.webchat.event import WebChatMessageEvent, resolve_to_me
from apeiria.webchat.protocol import InboundClear, InboundDelete, InboundMessage

if TYPE_CHECKING:
    from nonebot.adapters import Bot
    from nonebot.drivers import Driver

    from apeiria.db.models.conversation import Message as MessageRow

SELF_ID = "webchat"
_WS_NAME = "WebChat WS"
_CLOSE_UNAUTHORIZED = 1008  # policy violation


class WebChatAdapter(BaseAdapter):
    """WebChat 适配器：浏览器经 WebSocket 作为标准 NoneBot 适配器接入。"""

    def __init__(self, driver: Driver, **kwargs: Any) -> None:
        super().__init__(driver, **kwargs)
        self.connections = ConnectionManager()
        self._bot: WebChatBot | None = None
        self._conn_sessions: dict[str, str] = {}
        self._tasks: set[asyncio.Task[Any]] = set()
        self._setup()

    @classmethod
    def get_name(cls) -> str:
        return "WebChat"

    def _setup(self) -> None:
        cfg = get_webchat_config()
        if not cfg.enabled:
            logger.info("WebChat adapter disabled by config")
            return
        self.setup_websocket_server(
            WebSocketServerSetup(URL(cfg.ws_path), _WS_NAME, self._handle_ws)
        )
        logger.success("WebChat WS route registered at {}", cfg.ws_path)

    async def _call_api(self, bot: Bot, api: str, **data: Any) -> Any:  # noqa: ARG002
        logger.warning("WebChat adapter has no API: {}", api)
        return None

    def _default_session_id(self) -> str:
        return f"webchat:private:{resolve_default_user_id()}"

    async def _handle_ws(self, websocket: WebSocket) -> None:
        token = websocket.request.url.query.get("token") or ""
        username = await decode_token(token)
        if not username:
            await websocket.close(_CLOSE_UNAUTHORIZED, "unauthorized")
            return
        await websocket.accept()

        conn_id, _is_first = await self.connections.add(websocket)
        bot = self._ensure_bot()
        try:
            await self._replay_history(conn_id)
            while True:
                raw = await websocket.receive_text()
                await self._on_frame(bot, conn_id, raw)
        except WebSocketClosed:
            pass
        except Exception:  # noqa: BLE001
            logger.opt(exception=True).warning("WebChat ws handler error")
        finally:
            self._conn_sessions.pop(conn_id, None)
            if await self.connections.remove(conn_id):
                self._teardown_bot()

    def _ensure_bot(self) -> WebChatBot:
        if self._bot is None:
            self._bot = WebChatBot(self, SELF_ID, self.connections)
            self.bot_connect(self._bot)
        return self._bot

    def _teardown_bot(self) -> None:
        if self._bot is not None:
            self.bot_disconnect(self._bot)
            self._bot = None

    async def _replay_history(self, conn_id: str) -> None:
        cfg = get_webchat_config()
        session_id = self._default_session_id()
        rows = list(reversed(await load_recent(session_id, limit=cfg.history_limit)))
        messages = [self._row_to_wire(row, session_id) for row in rows]
        await self.connections.send_to(conn_id, protocol.history_frame(messages))

    def _row_to_wire(self, row: MessageRow, session_id: str) -> dict[str, Any]:
        meta = row.meta_json or {}
        segments = meta.get("segments")
        if not segments:
            segments = [{"type": "text", "text": row.content}] if row.content else []
        return protocol.wire_message(
            message_id=row.message_id or str(row.id),
            role=row.role,
            segments=segments,
            time=row.time,
            session_id=session_id,
            user_id=row.user_id,
        )

    async def _on_frame(self, bot: WebChatBot, conn_id: str, raw: str) -> None:
        try:
            frame = protocol.parse_inbound(json.loads(raw))
        except (json.JSONDecodeError, protocol.ProtocolError) as exc:
            await self.connections.send_to(
                conn_id, protocol.error_frame("bad_frame", str(exc))
            )
            return
        if isinstance(frame, InboundMessage):
            await self._on_message(bot, conn_id, frame)
        elif isinstance(frame, InboundClear):
            await self._on_clear(conn_id)
        elif isinstance(frame, InboundDelete):
            await self._on_delete(frame.message_id)

    async def _on_message(
        self, bot: WebChatBot, conn_id: str, frame: InboundMessage
    ) -> None:
        identity = frame.identity
        user_id = str(identity.get("user_id") or resolve_default_user_id())
        scene_type = identity.get("scene_type") or "private"
        if scene_type not in ("private", "group"):
            scene_type = "private"
        scene_id = str(identity.get("scene_id") or user_id)

        message = protocol.build_inbound_message(frame.text, frame.image)
        nicknames = nonebot.get_driver().config.nickname
        to_me = resolve_to_me(message, scene_type, nicknames)
        if scene_type == "group":
            session_id = f"webchat:group:{scene_id}"
        else:
            session_id = f"webchat:private:{user_id}"
        self._conn_sessions[conn_id] = session_id

        await ensure_session(session_id, "webchat", scene_type, scene_id)
        message_id = uuid4().hex
        segments = protocol.message_to_wire(message)
        await append_message(
            session_id=session_id,
            role="user",
            content=message.extract_plain_text(),
            user_id=user_id,
            message_id=message_id,
            meta_json={"segments": segments},
        )
        echo = protocol.wire_message(
            message_id=message_id,
            role="user",
            segments=segments,
            time=_now_iso(),
            session_id=session_id,
            user_id=user_id,
        )
        await self.connections.send_to(conn_id, protocol.message_frame(echo))

        event = WebChatMessageEvent(
            time=int(time.time()),
            self_id=SELF_ID,
            message_id=message_id,
            user_id=user_id,
            message=message,
            scene_type=scene_type,
            scene_id=scene_id,
            to_me=to_me,
            connection_id=conn_id,
        )
        task = asyncio.create_task(handle_event(bot, event))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _on_clear(self, conn_id: str) -> None:
        session_id = self._conn_sessions.get(conn_id) or self._default_session_id()
        await delete_session_messages(session_id)
        await self.connections.broadcast(protocol.cleared_frame())

    async def _on_delete(self, message_id: str) -> None:
        await delete_message(message_id)
        await self.connections.broadcast(protocol.deleted_frame(message_id))
