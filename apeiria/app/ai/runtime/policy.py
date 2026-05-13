"""Default runtime policy stage implementations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from apeiria.app.ai.runtime.planning.hard_rules import (
    decide_runtime_hard_rule,
    social_skip_to_runtime_decision,
)
from apeiria.app.ai.runtime.session.management import (
    managed_session_disabled_decision,
)
from apeiria.app.ai.runtime.stages import (
    RuntimeIngressInput,
    RuntimePolicyOutcome,
    RuntimeSocialDecisionInput,
)
from apeiria.app.ai.sessions.repository import AISessionManagementRepository

if TYPE_CHECKING:
    from datetime import datetime

    from apeiria.ai.model import AIModelBindingTarget
    from apeiria.ai.prompting import ReplyPersonaPromptBundleLike
    from apeiria.ai.tools import AIToolDefinition
    from apeiria.app.ai.reply_strategy.models import ReplyStrategyDecision, WakeContext
    from apeiria.app.ai.runtime.session.context import RuntimeTurnInput
    from apeiria.conversation.models import ChatContextMessageView


class RuntimeReplyDecider(Protocol):
    """Social reply policy collaborator for the default policy stage."""

    async def __call__(  # noqa: PLR0913
        self,
        *,
        turn: "RuntimeTurnInput",
        wake_context: "WakeContext | None",
        turns: list["ChatContextMessageView"],
        conversation_summary: str | None,
        relationship_context: str | None,
        persona: "ReplyPersonaPromptBundleLike | None",
        allowed_tools: tuple["AIToolDefinition", ...],
        initiative_bias: float,
        model_target: "AIModelBindingTarget",
        current_time: "datetime",
        trace_id: str,
    ) -> "ReplyStrategyDecision": ...


@dataclass(frozen=True, slots=True)
class RuntimePolicyDecisionStage:
    """Policy stage backed by runtime hard rules and reply strategy."""

    reply_decider: RuntimeReplyDecider
    session_repository: AISessionManagementRepository | None = None

    def evaluate(
        self,
        *,
        ingress_input: RuntimeIngressInput,
    ) -> RuntimePolicyOutcome:
        repository = self.session_repository or AISessionManagementRepository()
        managed_session = repository.get_session_sync(
            ingress_input.turn.identity.session_id
        )
        disabled_decision = (
            managed_session_disabled_decision(managed_session)
            if managed_session is not None
            else None
        )
        if disabled_decision is not None:
            source = ingress_input.turn.source
            return RuntimePolicyOutcome(
                stage="policy",
                source=source,
                decision=disabled_decision,
            )

        source = ingress_input.turn.source
        return RuntimePolicyOutcome(
            stage="policy",
            source=source,
            decision=decide_runtime_hard_rule(
                wake_context=ingress_input.wake_context,
                source=source,
                session_runtime=ingress_input.session_runtime,
                now=ingress_input.current_time,
            ),
        )

    async def decide_reply(
        self,
        *,
        social_input: RuntimeSocialDecisionInput,
    ) -> "ReplyStrategyDecision":
        turn = social_input.turn
        context = social_input.context.context
        return await self.reply_decider(
            turn=turn,
            wake_context=social_input.wake_context,
            turns=context.turns,
            conversation_summary=context.conversation_summary,
            relationship_context=context.relationship_context,
            persona=context.persona,
            allowed_tools=context.allowed_tools,
            initiative_bias=context.initiative_bias,
            model_target=context.model_target,
            current_time=social_input.current_time,
            trace_id=social_input.trace_id,
        )


__all__ = [
    "RuntimePolicyDecisionStage",
    "RuntimeReplyDecider",
    "social_skip_to_runtime_decision",
]
