"""Runtime-facing model gateway for AI services."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .service import ai_model_facade

if TYPE_CHECKING:
    from apeiria.ai.model.routing.bindings import AIModelBindingTarget
    from apeiria.ai.model.routing.models import AIModelRouteQuery
    from apeiria.ai.model.routing.selection import AISelectedModel

    from .adapter import (
        AIModelGenerateResponse,
        AIModelMessage,
        AIModelToolDefinition,
    )


class ModelGateway:
    """AI-internal model invocation boundary."""

    async def select_model(
        self,
        *,
        query: "AIModelRouteQuery | None" = None,
        target: "AIModelBindingTarget | None" = None,
    ) -> "AISelectedModel | None":
        return await ai_model_facade.select_model(query=query, target=target)

    @staticmethod
    def resolve_model_ref(selected: "AISelectedModel") -> str:
        model_name = ai_model_facade.resolve_model_name(selected) or "?"
        return f"{selected.source.source_id}:{model_name}"

    async def generate_native(
        self,
        *,
        selected: "AISelectedModel",
        prompt: str = "",
        messages: "tuple[AIModelMessage, ...]" = (),
        tools: "tuple[AIModelToolDefinition, ...]" = (),
    ) -> "AIModelGenerateResponse | None":
        """Invoke the provider and return its native response."""
        return await ai_model_facade.generate_text(
            selected,
            prompt=prompt,
            messages=messages,
            tools=tools,
        )


model_gateway = ModelGateway()
