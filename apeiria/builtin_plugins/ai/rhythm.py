from __future__ import annotations

import asyncio
import math
import random
import time
from typing import TYPE_CHECKING, Any

from nonebot.log import logger
from sqlalchemy import select

from apeiria.ai.agent.registry import _AgentEntry
from apeiria.db.engine import get_session
from apeiria.db.models.ai_settings import AIRuntimeSettings

if TYPE_CHECKING:
    from apeiria.ai.agent.registry import AgentRegistry

_DEBOUNCE_AT_MENTION = 5.0
_DEBOUNCE_PRIVATE = 6.0
_STALE_THRESHOLD = 3600
_TICK_RANGE_MIN = 12
_TICK_RANGE_MAX = 20


class SessionRhythm:
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.messages: list[Any] = []
        self.message_counter: int = 0
        self.last_message_at: float = time.monotonic()
        self.last_reply_at: float | None = None
        self.no_action_count: int = 0
        self.next_tick_at: float = time.monotonic() + random.uniform(
            _TICK_RANGE_MIN, _TICK_RANGE_MAX
        )
        self.recent_reply_timestamps: list[float] = []
        self._lock = asyncio.Lock()
        self._debounce_handle: asyncio.TimerHandle | None = None


class RhythmManager:
    def __init__(self, agent_registry: AgentRegistry) -> None:
        self._rhythms: dict[str, SessionRhythm] = {}
        self._agent_registry = agent_registry
        self._background_tasks: set[asyncio.Task[None]] = set()

    def on_message(
        self,
        session_id: str,
        message: Any,
        *,
        is_at_bot: bool = False,
        is_private: bool = False,
    ) -> None:
        rhythm = self._rhythms.get(session_id)
        if rhythm is None:
            rhythm = SessionRhythm(session_id)
            self._rhythms[session_id] = rhythm

        rhythm.messages.append(message)
        rhythm.message_counter += 1
        rhythm.last_message_at = time.monotonic()

        if is_at_bot or is_private:
            delay = _DEBOUNCE_PRIVATE if is_private else _DEBOUNCE_AT_MENTION
            if rhythm._debounce_handle is not None:
                rhythm._debounce_handle.cancel()
            loop = asyncio.get_event_loop()
            rhythm._debounce_handle = loop.call_later(
                delay,
                lambda sid=session_id: self._spawn(sid),
            )

    async def tick_all(self) -> None:
        now = time.monotonic()
        stale: list[str] = []

        for sid, rhythm in list(self._rhythms.items()):
            if now - rhythm.last_message_at > _STALE_THRESHOLD:
                stale.append(sid)
                continue

            if now < rhythm.next_tick_at:
                continue

            rhythm.next_tick_at = now + random.uniform(_TICK_RANGE_MIN, _TICK_RANGE_MAX)

            if rhythm._debounce_handle is not None:
                continue

            self._spawn(sid)

        for sid in stale:
            self._rhythms.pop(sid, None)

    async def try_proceed(  # noqa: C901, PLR0911
        self, session_id: str
    ) -> None:
        rhythm = self._rhythms.get(session_id)
        if rhythm is None:
            return

        if rhythm._lock.locked():
            return

        batch: list[Any] = []
        async with rhythm._lock:
            rhythm._debounce_handle = None

            async with get_session() as db:
                settings = (
                    await db.execute(
                        select(AIRuntimeSettings).where(AIRuntimeSettings.id == 1)
                    )
                ).scalar_one_or_none()
            if not settings:
                return

            entry = self._agent_registry._agents.get(session_id)
            if entry and entry.agent.is_streaming:
                return

            now = time.monotonic()
            if (
                rhythm.last_reply_at is not None
                and now - rhythm.last_reply_at < settings.cooldown_seconds
            ):
                return

            window_start = now - settings.reply_window_seconds
            rhythm.recent_reply_timestamps = [
                t for t in rhythm.recent_reply_timestamps if t > window_start
            ]
            if len(rhythm.recent_reply_timestamps) >= settings.max_replies_per_window:
                return

            trigger_threshold = math.ceil(1 / settings.talk_value)
            if rhythm.message_counter < trigger_threshold:
                return

            if rhythm.no_action_count > 0:
                backoff = min(
                    settings.no_action_backoff_base_seconds
                    * (2**rhythm.no_action_count),
                    settings.no_action_backoff_max_seconds,
                )
                if rhythm.last_reply_at and now - rhythm.last_reply_at < backoff:
                    return

            batch = rhythm.messages
            rhythm.messages = []
            rhythm.message_counter = 0

        if not batch:
            return

        try:
            await self._run_agent(session_id, rhythm)
        except Exception:  # noqa: BLE001
            logger.warning(
                "Rhythm proceed failed for %s",
                session_id,
                exc_info=True,
            )

    async def _run_agent(self, session_id: str, rhythm: SessionRhythm) -> None:
        from apeiria.ai.types import Message, SessionContext
        from apeiria.builtin_plugins.ai.agent_factory import build_agent
        from apeiria.conversation.models import SessionIdentity
        from apeiria.conversation.service import load_recent

        entry = self._agent_registry._agents.get(session_id)
        if entry:
            agent_obj = entry.agent
            entry.last_access = time.monotonic()
        else:
            agent_obj = await build_agent(session_id)
            if agent_obj is None:
                return
            self._agent_registry._agents[session_id] = _AgentEntry(
                agent=agent_obj, last_access=time.monotonic()
            )

        identity = SessionIdentity.parse(session_id)
        ctx = SessionContext(
            session_id=session_id,
            platform=identity.platform,
            scene_type=identity.scene_type,
            scene_id=identity.scene_id,
        )

        history = await load_recent(session_id)
        messages = [
            Message(role=m.role, content=m.content, user_id=m.user_id) for m in history
        ]

        result = await agent_obj.run(messages, ctx=ctx)

        if result.has_reply:
            rhythm.no_action_count = 0
            rhythm.last_reply_at = time.monotonic()
            rhythm.recent_reply_timestamps.append(time.monotonic())
        else:
            rhythm.no_action_count += 1

    def trigger(self, session_id: str) -> None:
        self._spawn(session_id)

    def _spawn(self, session_id: str) -> None:
        task = asyncio.ensure_future(self.try_proceed(session_id))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
