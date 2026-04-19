"""Statistics hook — record command usage after execution."""

from nonebot.adapters import Event
from nonebot.matcher import Matcher

from apeiria.app.statistics import statistics_service


async def stats_hook(
    matcher: Matcher,
    exception: Exception | None,
    event: Event,
) -> None:
    """Record command usage to CommandStatistics table."""
    await statistics_service.record_matcher_execution(
        matcher,
        event,
        success=exception is None,
    )
