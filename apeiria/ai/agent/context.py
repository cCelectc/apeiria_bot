from __future__ import annotations

from typing import TYPE_CHECKING

from nonebot.log import logger

if TYPE_CHECKING:
    from apeiria.ai.types import Message, PromptFragment, SessionContext


def assemble_prompt(
    fragments: list[PromptFragment],
    history: list[Message],
) -> list[dict[str, str]]:
    first = [f for f in fragments if f.placement == "first"]
    after = [f for f in fragments if f.placement == "after"]
    last = [f for f in fragments if f.placement == "last"]

    messages: list[dict[str, str]] = [
        {"role": f.role, "content": f.content} for f in first
    ]

    for m in history:
        msg: dict[str, str] = {"role": m.role, "content": m.content}
        if m.name:
            msg["name"] = m.name
        if m.tool_call_id:
            msg["tool_call_id"] = m.tool_call_id
        messages.append(msg)

    messages.extend({"role": f.role, "content": f.content} for f in after)
    messages.extend({"role": f.role, "content": f.content} for f in last)

    return messages


async def collect_fragments(
    ctx: SessionContext,
    handlers: list,
) -> list[PromptFragment]:
    fragments: list[PromptFragment] = []
    for handler in handlers:
        try:
            result = await handler(ctx)
            if result is not None:
                if not result.placement:
                    result.placement = "first"
                fragments.append(result)
        except Exception:  # noqa: BLE001, PERF203
            logger.warning(
                "Context handler %s failed",
                getattr(handler, "__name__", handler),
                exc_info=True,
            )
    return fragments
