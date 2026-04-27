"""AI domain status helpers used by the builtin AI plugin shell."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from apeiria.ai.model.routing.models import AIModelRouteQuery

if TYPE_CHECKING:
    from apeiria.ai.model import AIModelBindingTarget, AISelectedModel


@dataclass(frozen=True)
class AIServiceStatus:
    """Status payload for the currently loaded AI runtime."""

    phase: str
    summary: str
    ready: bool
    next_step: str | None = None


class _ModelGateway(Protocol):
    async def select_model(
        self,
        *,
        query: AIModelRouteQuery | None = None,
        target: "AIModelBindingTarget | None" = None,
    ) -> "AISelectedModel | None": ...


class AIService:
    """Service for reporting the current AI runtime status."""

    def __init__(self, model_gateway: _ModelGateway | None = None) -> None:
        self._model_gateway = model_gateway

    async def get_status(self) -> AIServiceStatus:
        selected = await self._resolve_default_reply_model()
        if selected is None:
            next_step = (
                "Configure or enable a chat model in AI Management, then make it "
                "available to the default reply path."
            )
            return AIServiceStatus(
                phase="runtime_degraded",
                ready=False,
                summary=f"Reply runtime is degraded. {next_step}",
                next_step=next_step,
            )

        return AIServiceStatus(
            phase="runtime_ready",
            ready=True,
            summary=(
                "AI reply generation has a selectable model: "
                f"{_format_selected_model(selected)}."
            ),
        )

    async def _resolve_default_reply_model(self) -> "AISelectedModel | None":
        gateway = self._model_gateway
        if gateway is None:
            from apeiria.ai.model import model_gateway

            gateway = model_gateway
        return await gateway.select_model(
            query=AIModelRouteQuery(task_class="reply_default"),
            target=None,
        )


def _format_selected_model(selected: "AISelectedModel") -> str:
    model_name = selected.resolved_model_name or selected.profile.model_id
    return f"{selected.source.source_id}:{model_name}"


ai_service = AIService()
