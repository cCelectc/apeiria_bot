"""Pure helpers for tool access policy evaluation."""

from __future__ import annotations

from apeiria.app.ai.tools.models import (
    AIToolPolicy,
    AIToolPolicyDecision,
    AIToolSpec,
)

_MAX_SUMMARY_TOOLS = 5


def evaluate_tool_policy(
    tool: AIToolSpec,
    policy: AIToolPolicy,
) -> AIToolPolicyDecision:
    """Return whether one tool is allowed under the given scene policy."""

    if not policy.execution_enabled:
        return AIToolPolicyDecision(
            allowed=False,
            reason="tool execution is disabled for this scene",
        )

    if tool.name in policy.denied_tool_names:
        return AIToolPolicyDecision(
            allowed=False,
            reason=f"tool '{tool.name}' is explicitly denied",
        )

    if (
        policy.allowed_tool_names is not None
        and tool.name not in policy.allowed_tool_names
    ):
        return AIToolPolicyDecision(
            allowed=False,
            reason=f"tool '{tool.name}' is not in the allowlist",
        )

    if tool.risk_level == "high" and not policy.allow_high_risk_tools:
        return AIToolPolicyDecision(
            allowed=False,
            reason=f"tool '{tool.name}' is high risk and not enabled",
        )

    if tool.is_capability_bridge and not policy.allow_capability_bridge:
        return AIToolPolicyDecision(
            allowed=False,
            reason="NoneBot capability bridge is not enabled",
        )

    return AIToolPolicyDecision(
        allowed=True,
        reason="allowed",
    )


def summarize_tool_policy(
    tools: list[AIToolSpec],
    policy: AIToolPolicy,
) -> str:
    """Build a compact textual summary of tool availability for prompts."""

    preauthorized_tools = [
        tool
        for tool in tools
        if policy.allowed_tool_names is None
        or tool.name in policy.allowed_tool_names
    ]
    if not policy.execution_enabled:
        if not preauthorized_tools:
            return (
                "No external tool execution is enabled in this reply path. "
                "Do not claim to have performed actions outside the visible "
                "chat context."
            )

        tool_list = ", ".join(
            tool.name for tool in preauthorized_tools[:_MAX_SUMMARY_TOOLS]
        )
        if len(preauthorized_tools) > _MAX_SUMMARY_TOOLS:
            tool_list += ", ..."
        return (
            "Tool execution is currently disabled in this reply path. "
            f"Pre-authorized tools for future execution: {tool_list}. "
            "Do not claim to have used any tools in this response."
        )

    allowed_tools = [
        tool
        for tool in tools
        if evaluate_tool_policy(tool, policy).allowed
    ]
    if not allowed_tools:
        return "No tools are currently allowed for this scene."

    tool_list = ", ".join(tool.name for tool in allowed_tools[:_MAX_SUMMARY_TOOLS])
    if len(allowed_tools) > _MAX_SUMMARY_TOOLS:
        tool_list += ", ..."
    return (
        "Tool use is restricted to explicitly allowed capabilities. "
        f"Allowed tools in this scene: {tool_list}. "
        "Do not claim to have used tools that are not listed here."
    )
