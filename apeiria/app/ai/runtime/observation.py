"""Default runtime observation stage implementations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from datetime import datetime

    from apeiria.app.ai.runtime.session.context import RuntimeTurnInput
    from apeiria.app.ai.runtime.stages import RuntimeIngressInput
    from apeiria.conversation.models import ChatSessionIdentity


class RuntimeObservationEffects(Protocol):
    """Observation side-effect collaborator for the default observation stage."""

    async def __call__(
        self,
        *,
        turn: "RuntimeTurnInput",
        current_time: "datetime",
    ) -> None: ...


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


__all__ = [
    "RuntimeObservationEffects",
    "RuntimeObservationEffectsStage",
    "RuntimeObservedTurnPersistence",
]
