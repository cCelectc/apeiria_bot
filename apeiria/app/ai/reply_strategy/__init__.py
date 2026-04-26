"""Unified reply strategy pipeline for the AI runtime.

Three layers:
1. Wake Gate   — pure rules, zero cost
2. Initiative  — per-session budget, no LLM
3. Social Judgment — LLM-backed behavioral decision
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .helpers import (
        count_recent_bot_turns,
        latest_bot_turn_at,
        latest_user_turn_text,
    )
    from .models import (
        InitiativeBudgetResult,
        InitiativeState,
        ReplyStrategyAction,
        ReplyStrategyDecision,
        ReplyStrategyDecisionSource,
        SocialJudgmentAction,
        SocialJudgmentInput,
        SocialJudgmentResult,
        SocialJudgmentToolMode,
        WakeContext,
        WakeEngagement,
        WakeSignal,
        judgment_to_decision,
    )
    from .service import (
        ReplyStrategyService,
        reply_strategy_service,
        summarize_reply_strategy_decision,
    )
    from .wake_gate import build_wake_context

__all__ = [
    "InitiativeBudgetResult",
    "InitiativeState",
    "ReplyStrategyAction",
    "ReplyStrategyDecision",
    "ReplyStrategyDecisionSource",
    "ReplyStrategyService",
    "SocialJudgmentAction",
    "SocialJudgmentInput",
    "SocialJudgmentResult",
    "SocialJudgmentToolMode",
    "WakeContext",
    "WakeEngagement",
    "WakeSignal",
    "build_wake_context",
    "count_recent_bot_turns",
    "judgment_to_decision",
    "latest_bot_turn_at",
    "latest_user_turn_text",
    "reply_strategy_service",
    "summarize_reply_strategy_decision",
]

_LAZY_EXPORTS: dict[str, str] = {
    "InitiativeBudgetResult": ".models",
    "InitiativeState": ".models",
    "ReplyStrategyAction": ".models",
    "ReplyStrategyDecision": ".models",
    "ReplyStrategyDecisionSource": ".models",
    "SocialJudgmentAction": ".models",
    "SocialJudgmentInput": ".models",
    "SocialJudgmentResult": ".models",
    "SocialJudgmentToolMode": ".models",
    "WakeContext": ".models",
    "WakeEngagement": ".models",
    "WakeSignal": ".models",
    "judgment_to_decision": ".models",
    "ReplyStrategyService": ".service",
    "reply_strategy_service": ".service",
    "summarize_reply_strategy_decision": ".service",
    "build_wake_context": ".wake_gate",
    "count_recent_bot_turns": ".helpers",
    "latest_bot_turn_at": ".helpers",
    "latest_user_turn_text": ".helpers",
}


def __getattr__(name: str) -> Any:
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(name)
    module = import_module(module_name, __name__)
    return getattr(module, name)
