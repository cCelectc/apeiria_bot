"""Runtime-facing model gateway wrapping the AI compat profile."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from apeiria.app.runtime.effect import (
    Effect,
    current_effect_queue,
    new_effect,
)
from apeiria.app.runtime.models import ModelRequest, ModelResponse, ToolCall
from apeiria.app.runtime.observer import current_request_id

from .service import ai_model_facade

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from .adapter import (
        AIModelGenerateResponse,
        AIModelMessage,
        AIModelToolDefinition,
    )
    from .bindings import AIModelBindingTarget
    from .models import AIModelRouteQuery
    from .selection import AISelectedModel


_PROVIDER = "ai_runtime"


def _tool_calls_view(
    response: "AIModelGenerateResponse | None",
) -> tuple[ToolCall, ...]:
    if response is None:
        return ()
    return tuple(
        ToolCall(
            tool_call_id=call.tool_call_id,
            name=call.name,
            arguments=dict(call.arguments or {}),
        )
        for call in response.tool_calls
    )


def _usage_view(response: "AIModelGenerateResponse") -> dict[str, Any]:
    raw = response.raw
    if not isinstance(raw, dict):
        return {}
    usage = raw.get("usage")
    return dict(usage) if isinstance(usage, dict) else {}


class ModelGateway:
    """Unified model invocation boundary for runtime callers."""

    async def select_model(
        self,
        session: "AsyncSession",
        *,
        query: "AIModelRouteQuery | None" = None,
        target: "AIModelBindingTarget | None" = None,
    ) -> "AISelectedModel | None":
        return await ai_model_facade.select_model(session, query=query, target=target)

    @staticmethod
    def resolve_model_ref(selected: "AISelectedModel") -> str:
        model_name = ai_model_facade.resolve_model_name(selected) or "?"
        return f"{selected.source.source_id}:{model_name}"

    async def generate(
        self,
        request: ModelRequest,
        *,
        selected: "AISelectedModel",
        origin: str = "ai_runtime.model_gateway",
    ) -> ModelResponse | None:
        """Invoke the underlying provider and project to a `ModelResponse`."""

        effect = self._record_effect(
            origin=origin,
            payload={
                "provider": request.provider,
                "model_ref": request.model_ref,
                "trace_id": request.trace_id,
                "tool_count": len(request.tools),
                "message_count": len(request.messages),
                "has_prompt": bool(request.prompt),
            },
        )
        try:
            response = await ai_model_facade.generate_text(
                selected,
                prompt=request.prompt,
                messages=request.messages,  # type: ignore[arg-type]
                tools=request.tools,  # type: ignore[arg-type]
            )
        except Exception as exc:
            effect.mark_failed(str(exc))
            raise

        if response is None:
            effect.mark_dropped("model_returned_none")
            return None

        projected = ModelResponse(
            provider=request.provider,
            model_ref=request.model_ref,
            source_id=response.source_id,
            content=response.content or "",
            tool_calls=_tool_calls_view(response),
            usage=_usage_view(response),
            native_response=response,
        )
        effect.mark_flushed(
            {
                "model_name": response.model_name,
                "source_id": response.source_id,
                "tool_call_count": len(projected.tool_calls),
                "usage": projected.usage,
            }
        )
        return projected

    async def generate_native(  # noqa: PLR0913
        self,
        *,
        selected: "AISelectedModel",
        prompt: str = "",
        messages: "tuple[AIModelMessage, ...]" = (),
        tools: "tuple[AIModelToolDefinition, ...]" = (),
        trace_id: str | None = None,
        labels: tuple[str, ...] = (),
        origin: str = "ai_runtime.model_gateway",
    ) -> "AIModelGenerateResponse | None":
        """Compat entry point — takes native AI types, records the effect."""

        request = ModelRequest(
            provider=_PROVIDER,
            model_ref=self.resolve_model_ref(selected),
            trace_id=trace_id,
            prompt=prompt,
            messages=messages,
            tools=tools,
            labels=labels,
        )
        response = await self.generate(request, selected=selected, origin=origin)
        return response.native_response if response is not None else None

    @staticmethod
    def _record_effect(*, origin: str, payload: dict[str, Any]) -> Effect:
        effect = new_effect(
            kind="model_request",
            origin=origin,
            request_id=current_request_id(),
            payload=payload,
        )
        queue = current_effect_queue()
        if queue is not None:
            queue.enqueue(effect)
        return effect


model_gateway = ModelGateway()
