"""Statistics hook — no-op placeholder (DB write removed in TraceBroker redesign)."""

from nonebot.adapters import Event
from nonebot.matcher import Matcher


async def stats_hook(
    matcher: Matcher,
    exception: Exception | None,
    event: Event,
) -> None:
    pass
