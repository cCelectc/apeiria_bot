"""Decorator-registered QQ AI tools."""

from __future__ import annotations

from typing import Literal

from apeiria.ai.plugin_api import ai_tool, live_platform_context
from apeiria.ai.tools.models import AIToolExecutionContext, AIToolLevel, AIToolResult

from .providers import (
    QQActionResult,
    QQReaction,
    qq_tool_provider_registry,
)

ReactionChoice = Literal["like"]


@ai_tool(
    name="qq.poke",
    description="Poke the current QQ message actor when this live scene supports it.",
    required_level=AIToolLevel.WRITE,
)
async def poke(
    *,
    context: AIToolExecutionContext,  # noqa: ARG001
) -> AIToolResult:
    """Poke the current actor through the active QQ provider."""

    live = live_platform_context()
    if live is None:
        return _not_ready("runtime_missing_capability")

    provider = qq_tool_provider_registry.resolve(live.bot, live.event)
    if provider is None:
        return _not_ready("unsupported_adapter")

    result = await provider.poke_current_actor(live.bot, live.event)
    return _tool_result("qq.poke", result)


@ai_tool(
    name="qq.react_to_message",
    description="React to the current/source QQ message with a bounded reaction.",
    required_level=AIToolLevel.WRITE,
)
async def react_to_message(
    reaction: ReactionChoice = "like",
    *,
    context: AIToolExecutionContext,  # noqa: ARG001
) -> AIToolResult:
    """React to the current/source message through the active QQ provider."""

    live = live_platform_context()
    if live is None:
        return _not_ready("runtime_missing_capability")

    provider = qq_tool_provider_registry.resolve(live.bot, live.event)
    if provider is None:
        return _not_ready("unsupported_adapter")

    result = await provider.react_to_message(
        live.bot,
        live.event,
        reaction=_coerce_reaction(reaction),
    )
    return _tool_result("qq.react_to_message", result)


def _coerce_reaction(reaction: ReactionChoice) -> QQReaction:
    return reaction


def _not_ready(reason: str) -> AIToolResult:
    return AIToolResult(
        summary=f"- [qq_tools] not executed: {reason}",
        output_payload={"status": "not_ready", "reason": reason},
        status="not_ready",
    )


def _tool_result(tool_name: str, result: QQActionResult) -> AIToolResult:
    payload = {"status": result.status}
    if result.reason is not None:
        payload["reason"] = result.reason

    if result.success:
        return AIToolResult(
            summary=f"- [{tool_name}] completed",
            output_payload=payload,
            status="success",
        )
    if result.status == "unsupported":
        return AIToolResult(
            summary=f"- [{tool_name}] not executed: {result.reason or 'unsupported'}",
            output_payload=payload,
            status="not_ready",
        )
    return AIToolResult(
        summary=f"- [{tool_name}] failed: {result.reason or 'operation_failed'}",
        output_payload=payload,
        status="error",
    )


__all__ = ["poke", "react_to_message"]
