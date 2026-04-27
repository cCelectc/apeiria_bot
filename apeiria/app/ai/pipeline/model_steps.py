"""Runtime model selection and generation steps."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from nonebot.log import logger

from apeiria.ai.model import AIModelRouteQuery, model_gateway

if TYPE_CHECKING:
    from apeiria.ai.model import (
        AIModelBindingTarget,
        AIModelGenerateResponse,
        AIModelTaskClass,
        AIModelToolDefinition,
        AISelectedModel,
    )


@dataclass(frozen=True)
class GenerationRequest:
    """One model generation request with trace metadata."""

    selected: "AISelectedModel"
    prompt: str
    trace_id: str
    session_id: str
    tools: tuple["AIModelToolDefinition", ...]
    failure_stage: str


async def select_pipeline_model(
    *,
    task_class: "AIModelTaskClass",
    target: "AIModelBindingTarget",
) -> "AISelectedModel | None":
    return await model_gateway.select_model(
        query=AIModelRouteQuery(task_class=task_class),
        target=target,
    )


async def safe_generate_model(
    request: GenerationRequest,
) -> "AIModelGenerateResponse | None":
    try:
        return await model_gateway.generate_native(
            selected=request.selected,
            prompt=request.prompt,
            tools=request.tools,
        )
    except Exception as exc:  # noqa: BLE001
        logger.opt(exception=exc).warning(
            "AI trace {} {} for session {}",
            request.trace_id,
            request.failure_stage,
            request.session_id,
        )
        return None
