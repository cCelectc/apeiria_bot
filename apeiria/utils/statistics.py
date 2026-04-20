"""Statistics application services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from nonebot.log import logger

from apeiria.access.level import extract_group_id

if TYPE_CHECKING:
    from nonebot.adapters import Event
    from nonebot.matcher import Matcher


@dataclass(frozen=True)
class StatsContext:
    """Execution context required for statistics persistence."""

    user_id: str
    group_id: str | None


class StatisticsService:
    """Record command execution results."""

    async def record_matcher_execution(
        self,
        matcher: Matcher,
        event: Event,
        *,
        success: bool,
    ) -> None:
        plugin = matcher.plugin
        if plugin is None:
            return

        context = await self._build_context_for_stats(event)
        if context is None:
            return

        command = self._extract_command_name(matcher) or plugin.name

        try:
            from nonebot_plugin_orm import get_session

            from apeiria.db.models.statistics import CommandStatistics

            async with get_session() as session:
                session.add(
                    CommandStatistics(
                        plugin_name=plugin.module_name,
                        command=command,
                        user_id=context.user_id,
                        group_id=context.group_id,
                        success=success,
                    )
                )
                await session.commit()
        except Exception:  # noqa: BLE001
            logger.debug("Failed to record command statistics")

    async def _build_context_for_stats(self, event: Event) -> StatsContext | None:
        try:
            user_id = event.get_user_id()
        except Exception:  # noqa: BLE001
            return None

        group_id = getattr(event, "group_id", None)
        if group_id is None:
            try:
                group_id = extract_group_id(
                    event.get_session_id(),
                    user_id,
                )
            except Exception:  # noqa: BLE001
                group_id = None

        return StatsContext(
            user_id=user_id,
            group_id=str(group_id) if group_id is not None else None,
        )

    def _extract_command_name(self, matcher: Matcher) -> str:
        if hasattr(matcher, "state") and matcher.state:
            cmd = matcher.state.get("_prefix", {}).get("command", ())
            if cmd:
                return " ".join(cmd) if isinstance(cmd, tuple) else str(cmd)
        return ""


statistics_service = StatisticsService()
