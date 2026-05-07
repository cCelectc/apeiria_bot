"""Default runtime observation stage implementations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from datetime import datetime

    from apeiria.app.ai.runtime.session.context import RuntimeTurnInput
    from apeiria.app.ai.runtime.stages import RuntimeIngressInput


class RuntimeObservationEffects(Protocol):
    """Observation side-effect collaborator for the default observation stage."""

    async def __call__(
        self,
        *,
        turn: "RuntimeTurnInput",
        current_time: "datetime",
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class RuntimeObservationEffectsStage:
    """Observation side-effect stage for live writes before context reads."""

    apply_observation_effects: RuntimeObservationEffects | None = None

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


__all__ = ["RuntimeObservationEffects", "RuntimeObservationEffectsStage"]
