"""Decorator-registered QQ AI tools."""

from __future__ import annotations

from typing import Literal

from apeiria.ai.plugin_api import ai_tool, live_platform_context
from apeiria.ai.tools.models import AIToolExecutionContext, AIToolLevel, AIToolResult

from .providers import (
    QQActionResult,
    QQGroupMemberLookupResult,
    QQMentionFragmentResult,
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


@ai_tool(
    name="qq.get_group_members",
    description=(
        "Find current QQ group members by QQ id, nickname, or group card before "
        "mentioning someone."
    ),
    required_level=AIToolLevel.WRITE,
)
async def get_group_members(
    keyword: str = "",
    *,
    context: AIToolExecutionContext,  # noqa: ARG001
) -> AIToolResult:
    """Look up current group members through the active QQ provider."""

    live = live_platform_context()
    if live is None:
        return _not_ready("runtime_missing_capability")

    provider = qq_tool_provider_registry.resolve(live.bot, live.event)
    if provider is None:
        return _not_ready("unsupported_adapter")

    result = await provider.get_group_members(
        live.bot,
        live.event,
        keyword=keyword,
    )
    return _member_lookup_tool_result(result)


@ai_tool(
    name="qq.mention_user",
    description=(
        "Create a real QQ mention fragment for one confirmed numeric QQ user id."
    ),
    required_level=AIToolLevel.WRITE,
)
async def mention_user(
    user_id: str,
    *,
    context: AIToolExecutionContext,  # noqa: ARG001
) -> AIToolResult:
    """Return a provider-normalized mention fragment for the normal reply."""

    live = live_platform_context()
    if live is None:
        return _not_ready("runtime_missing_capability")

    provider = qq_tool_provider_registry.resolve(live.bot, live.event)
    if provider is None:
        return _not_ready("unsupported_adapter")

    result = await provider.mention_user(
        live.bot,
        live.event,
        user_id=user_id,
    )
    return _mention_tool_result(result)


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


def _member_lookup_tool_result(result: QQGroupMemberLookupResult) -> AIToolResult:
    payload: dict[str, object] = {
        "status": result.status,
        "group_id": result.group_id,
        "count": len(result.members),
        "total_matches": result.total_matches,
        "truncated": result.truncated,
        "members": [member.to_payload() for member in result.members],
    }
    if result.reason is not None:
        payload["reason"] = result.reason

    if result.success:
        return AIToolResult(
            summary=(
                "- [qq.get_group_members] found "
                f"{len(result.members)}/{result.total_matches} member(s): "
                f"{_format_member_summary(result)}"
            ),
            output_payload=payload,
            status="success",
        )
    if result.status == "unsupported":
        return AIToolResult(
            summary=(
                "- [qq.get_group_members] not executed: "
                f"{result.reason or 'unsupported'}"
            ),
            output_payload=payload,
            status="not_ready",
        )
    return AIToolResult(
        summary=(
            f"- [qq.get_group_members] failed: {result.reason or 'operation_failed'}"
        ),
        output_payload=payload,
        status="error",
    )


def _mention_tool_result(result: QQMentionFragmentResult) -> AIToolResult:
    payload = {
        "status": result.status,
        "user_id": result.user_id,
        "mention": result.mention,
    }
    if result.reason is not None:
        payload["reason"] = result.reason

    if result.success:
        return AIToolResult(
            summary=(
                "- [qq.mention_user] mention fragment ready: "
                f"user_id={result.user_id}, mention={result.mention}"
            ),
            output_payload=payload,
            status="success",
        )
    if result.status == "unsupported":
        return AIToolResult(
            summary=(
                f"- [qq.mention_user] not executed: {result.reason or 'unsupported'}"
            ),
            output_payload=payload,
            status="not_ready",
        )
    return AIToolResult(
        summary=f"- [qq.mention_user] failed: {result.reason or 'operation_failed'}",
        output_payload=payload,
        status="error",
    )


def _format_member_summary(result: QQGroupMemberLookupResult) -> str:
    if not result.members:
        return "no matching members"

    member_lines = [
        (
            "user_id={user_id}, nickname={nickname}, group_card={group_card}, "
            "role={role}"
        ).format(
            user_id=member.user_id,
            nickname=member.nickname or "<empty>",
            group_card=member.group_card or "<empty>",
            role=member.role or "member",
        )
        for member in result.members
    ]
    suffix = " (truncated)" if result.truncated else ""
    return "; ".join(member_lines) + suffix


__all__ = ["get_group_members", "mention_user", "poke", "react_to_message"]
