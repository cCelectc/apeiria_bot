"""Default runtime observation stage implementations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from datetime import datetime

    from apeiria.ai.memory import AIMemoryExtractionResult, AIObservationLevel
    from apeiria.app.ai.runtime.session.context import RuntimeTurnInput
    from apeiria.app.ai.runtime.stages import RuntimeIngressInput
    from apeiria.app.ai.runtime.strategy import RuntimeHardRuleDecision
    from apeiria.conversation.models import ChatSessionIdentity


class RuntimeObservationEffects(Protocol):
    """Observation side-effect collaborator for the default observation stage."""

    async def __call__(
        self,
        *,
        turn: "RuntimeTurnInput",
        current_time: "datetime",
    ) -> None: ...


class RuntimeDeepObservationEffects(Protocol):
    """Deep observation collaborator for governed memory interpretation."""

    async def __call__(
        self,
        *,
        turn: "RuntimeTurnInput",
    ) -> "AIMemoryExtractionResult": ...


class RuntimeObservedTurnPersistence(Protocol):
    """Persistence collaborator for observed non-reply turns."""

    async def __call__(
        self,
        *,
        identity: "ChatSessionIdentity",
        source_message_id: str | None,
        author_id: str,
        text_content: str,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class RuntimeObservationEffectsStage:
    """Observation side-effect stage for live writes before context reads."""

    apply_observation_effects: RuntimeObservationEffects | None = None
    persist_observed_turn: RuntimeObservedTurnPersistence | None = None
    apply_deep_observation_effects: RuntimeDeepObservationEffects | None = None

    async def apply(
        self,
        *,
        ingress_input: "RuntimeIngressInput",
    ) -> None:
        if self.apply_observation_effects is None:
            return
        await self.apply_observation_effects(
            turn=ingress_input.turn,
            current_time=ingress_input.current_time,
        )

    async def apply_deep_observation(
        self,
        *,
        ingress_input: "RuntimeIngressInput",
    ) -> "AIMemoryExtractionResult | None":
        if self.apply_deep_observation_effects is None:
            return None
        return await self.apply_deep_observation_effects(turn=ingress_input.turn)

    async def apply_observed_turn(
        self,
        *,
        ingress_input: "RuntimeIngressInput",
    ) -> None:
        if self.persist_observed_turn is None:
            return
        turn = ingress_input.turn
        await self.persist_observed_turn(
            identity=turn.identity,
            source_message_id=turn.source_message_id,
            author_id=turn.user_id,
            text_content=turn.message_text,
        )


def classify_observation_level(
    decision: "RuntimeHardRuleDecision",
) -> "AIObservationLevel":
    """Map runtime policy decisions to memory observation depth."""

    if decision.action == "drop" or not decision.should_observe:
        return "drop"
    if _bool_evidence(decision, "observe_deep"):
        return "observe_deep"
    if decision.should_reply and decision.action == "continue":
        if _is_direct_engagement(decision):
            return "engage"
        return "observe_light"
    return "observe_light"


def _is_direct_engagement(decision: "RuntimeHardRuleDecision") -> bool:
    direct_reasons = {"direct_signal", "private_message", "future_task"}
    if direct_reasons.intersection(decision.reason_codes):
        return True
    return bool(
        _bool_evidence(decision, "direct_signal")
        or _bool_evidence(decision, "is_private")
        or decision.evidence.get("runtime_mode") == "future_task"
    )


def _bool_evidence(decision: "RuntimeHardRuleDecision", key: str) -> bool:
    return decision.evidence.get(key) is True


__all__ = [
    "RuntimeDeepObservationEffects",
    "RuntimeObservationEffects",
    "RuntimeObservationEffectsStage",
    "RuntimeObservedTurnPersistence",
    "classify_observation_level",
]
