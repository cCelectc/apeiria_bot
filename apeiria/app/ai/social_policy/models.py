"""Models for explicit social-policy decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from datetime import datetime

    from apeiria.app.ai.model.models import AIModelTaskClass

AISocialPolicySceneType = Literal["private", "group"]
AISocialPolicyAction = Literal["reply", "interject", "wait", "suppress"]
AISocialPolicyToolMode = Literal["allow", "avoid"]
AISocialPolicyRuntimeMode = Literal["message", "future_task"]


@dataclass(frozen=True)
class AISocialPolicyInput:
    """Normalized facts used by the social-policy layer."""

    conversation_id: str
    scene_type: AISocialPolicySceneType
    message_text: str
    latest_user_turn_text: str | None
    conversation_summary: str | None
    relationship_context: str | None
    persona_id: str | None
    available_tool_names: tuple[str, ...]
    recent_turn_count: int
    recent_bot_turn_count: int
    last_bot_turn_at: datetime | None
    current_time: datetime
    runtime_mode: AISocialPolicyRuntimeMode
    is_direct_wake: bool


@dataclass(frozen=True)
class AISocialPolicyDecision:
    """Structured social decision produced before reply generation."""

    action: AISocialPolicyAction
    should_speak: bool
    should_interject: bool
    should_wait: bool
    tool_mode: AISocialPolicyToolMode
    reason_codes: tuple[str, ...]
    reason_text: str
    evidence: dict[str, object]



def resolve_social_policy_task_class() -> "AIModelTaskClass":
    """Return the model task class used for social-policy judgment."""

    return "planner_light"



def build_fallback_social_policy_decision(
    policy_input: AISocialPolicyInput,
) -> AISocialPolicyDecision:
    """Return the conservative fallback decision when LLM judgment is unavailable."""

    reason_text = (
        "Social policy model was unavailable, so the runtime used a "
        "conservative fallback."
    )
    action: AISocialPolicyAction = (
        "reply"
        if policy_input.runtime_mode == "future_task"
        or policy_input.scene_type == "private"
        or policy_input.is_direct_wake
        else "suppress"
    )
    should_speak = action in {"reply", "interject"}
    return AISocialPolicyDecision(
        action=action,
        should_speak=should_speak,
        should_interject=False,
        should_wait=False,
        tool_mode="avoid",
        reason_codes=("fallback_social_policy",),
        reason_text=reason_text,
        evidence={
            "scene_type": policy_input.scene_type,
            "runtime_mode": policy_input.runtime_mode,
            "is_direct_wake": policy_input.is_direct_wake,
            "available_tool_names": list(policy_input.available_tool_names),
            "policy_source": "fallback",
        },
    )
