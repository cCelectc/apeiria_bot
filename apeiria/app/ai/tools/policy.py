"""Pure helpers for tool access policy evaluation."""

from __future__ import annotations

from apeiria.app.ai.tools.models import (
    AIToolPolicy,
    AIToolPolicyDecision,
    AIToolSpec,
)


def evaluate_tool_policy(
    tool: AIToolSpec,
    policy: AIToolPolicy,
) -> AIToolPolicyDecision:
    """Return whether one tool is allowed under the given scene policy."""

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
