"""Default runtime context assembly stage implementations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from apeiria.app.ai.runtime.stages import RuntimeContextBundle, RuntimeIngressInput

if TYPE_CHECKING:
    from datetime import datetime

    from apeiria.app.ai.runtime.session.context import (
        RuntimeContextMaterials,
        RuntimeTurnInput,
    )


class RuntimeContextCollector(Protocol):
    """Context-material collector for the default context stage."""

    async def __call__(
        self,
        turn: "RuntimeTurnInput",
        current_time: "datetime",
    ) -> "RuntimeContextMaterials": ...


@dataclass(frozen=True, slots=True)
class RuntimeContextAssemblyStage:
    """Context assembly stage backed by the reply input collector."""

    gather_reply_inputs: RuntimeContextCollector

    async def assemble(
        self,
        *,
        ingress_input: RuntimeIngressInput,
    ) -> RuntimeContextBundle:
        inputs = await self.gather_reply_inputs(
            ingress_input.turn,
            ingress_input.current_time,
        )
        return RuntimeContextBundle(stage="context", context=inputs)


__all__ = ["RuntimeContextAssemblyStage", "RuntimeContextCollector"]
