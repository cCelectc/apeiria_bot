from __future__ import annotations

import time
from typing import TYPE_CHECKING

from nonebot.log import logger

if TYPE_CHECKING:
    from collections.abc import Callable

    from apeiria.ai.agent.agent import Agent

_TTL_SECONDS = 24 * 60 * 60
_SWEEP_INTERVAL = 5 * 60


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, _AgentEntry] = {}

    def get_or_create(
        self,
        session_id: str,
        factory: Callable[[str], Agent],
    ) -> Agent:
        entry = self._agents.get(session_id)
        if entry:
            entry.last_access = time.monotonic()
            return entry.agent
        agent = factory(session_id)
        self._agents[session_id] = _AgentEntry(
            agent=agent,
            last_access=time.monotonic(),
        )
        return agent

    def remove(self, session_id: str) -> None:
        self._agents.pop(session_id, None)

    def sweep_expired(self) -> int:
        now = time.monotonic()
        expired = [
            sid
            for sid, entry in self._agents.items()
            if (now - entry.last_access) > _TTL_SECONDS and not entry.agent.is_streaming
        ]
        for sid in expired:
            self._agents.pop(sid, None)
        if expired:
            logger.info("Swept {} expired agents", len(expired))
        return len(expired)

    @property
    def active_count(self) -> int:
        return len(self._agents)


class _AgentEntry:
    __slots__ = ("agent", "last_access")

    def __init__(self, agent: Agent, last_access: float) -> None:
        self.agent = agent
        self.last_access = last_access
