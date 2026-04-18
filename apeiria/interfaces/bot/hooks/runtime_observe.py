"""Runtime observation hook — build DispatchRequest / ExecutionReport."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nonebot.message import run_postprocessor, run_preprocessor

from apeiria.app.runtime import runtime_matcher_observer

if TYPE_CHECKING:
    from nonebot.adapters import Bot, Event
    from nonebot.matcher import Matcher


@run_preprocessor
async def runtime_observe_pre(
    matcher: "Matcher",
    event: "Event",
    bot: "Bot",
) -> None:
    """Build a `DispatchRequest` and bind it to the matcher run."""

    runtime_matcher_observer.observe_pre_run(matcher, bot, event)


@run_postprocessor
async def runtime_observe_post(
    matcher: "Matcher",
    exception: Exception | None,
) -> None:
    """Seal the `ExecutionReport` after the matcher completes."""

    runtime_matcher_observer.observe_post_run(matcher, exception)
