"""Social-policy boundary for AI runtime behavior decisions."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .models import (
        AISocialPolicyAction,
        AISocialPolicyDecision,
        AISocialPolicyInput,
        AISocialPolicySceneType,
        AISocialPolicyToolMode,
        build_fallback_social_policy_decision,
        resolve_social_policy_task_class,
    )
    from .parsing import build_social_policy_prompt, parse_social_policy_response
    from .service import (
        ai_social_policy_service,
        count_recent_bot_turns,
        latest_bot_turn_at,
        latest_user_turn_text,
        summarize_social_policy_decision,
    )

__all__ = [
    "AISocialPolicyAction",
    "AISocialPolicyDecision",
    "AISocialPolicyInput",
    "AISocialPolicySceneType",
    "AISocialPolicyToolMode",
    "ai_social_policy_service",
    "build_fallback_social_policy_decision",
    "build_social_policy_prompt",
    "count_recent_bot_turns",
    "latest_bot_turn_at",
    "latest_user_turn_text",
    "parse_social_policy_response",
    "resolve_social_policy_task_class",
    "summarize_social_policy_decision",
]

_LAZY_EXPORTS = {
    "AISocialPolicyAction": ".models",
    "AISocialPolicyDecision": ".models",
    "AISocialPolicyInput": ".models",
    "AISocialPolicySceneType": ".models",
    "AISocialPolicyToolMode": ".models",
    "build_fallback_social_policy_decision": ".models",
    "resolve_social_policy_task_class": ".models",
    "build_social_policy_prompt": ".parsing",
    "parse_social_policy_response": ".parsing",
    "ai_social_policy_service": ".service",
    "count_recent_bot_turns": ".service",
    "latest_bot_turn_at": ".service",
    "latest_user_turn_text": ".service",
    "summarize_social_policy_decision": ".service",
}


def __getattr__(name: str) -> Any:
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(name)
    module = import_module(module_name, __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value
