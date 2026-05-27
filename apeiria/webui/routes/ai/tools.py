"""AI executable tools observation routes."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from apeiria.ai.tools import AIToolPolicy, coerce_tool_level
from apeiria.ai.tools.exposure import create_tool_exposure_plan
from apeiria.app.ai import ai_application
from apeiria.webui.auth import require_auth

from .tools_schemas import (
    AIToolExecutionItem,
    AIToolItem,
    to_ai_tool_execution_item,
    to_ai_tool_item,
)

router = APIRouter()


@router.get("/tools", response_model=list[AIToolItem])
async def list_ai_tools(
    _: Annotated[Any, Depends(require_auth)],
    *,
    allowed_only: Annotated[bool, Query()] = False,
    allowed_level: Annotated[str | None, Query()] = None,
) -> list[AIToolItem]:
    policy = (
        AIToolPolicy(allowed_level=coerce_tool_level(allowed_level))
        if allowed_level is not None
        else AIToolPolicy()
        if allowed_only
        else None
    )
    tools = ai_application.operations.list_tools(policy=None)
    if policy is None:
        return [to_ai_tool_item(item) for item in tools]

    exposure = create_tool_exposure_plan(
        tools=tuple(tools),
        policy=policy,
        model_supports_tools=True,
    )
    visible = {tool.name for tool in exposure.visible_tools}
    return [
        to_ai_tool_item(
            item,
            status=_tool_status(
                item.name,
                visible=visible,
                unavailable=exposure.unavailable_reasons,
                denied=exposure.denied_reasons,
            ),
            denied_reason=exposure.denied_reasons.get(item.name),
            unavailable_reason=exposure.unavailable_reasons.get(item.name),
        )
        for item in tools
    ]


@router.get("/tools/executions/recent", response_model=list[AIToolExecutionItem])
async def list_recent_ai_tool_executions(
    _: Annotated[Any, Depends(require_auth)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[AIToolExecutionItem]:
    rows = await ai_application.operations.list_recent_tool_executions(limit=limit)
    return [to_ai_tool_execution_item(item) for item in rows]


__all__ = ["router"]


def _tool_status(
    name: str,
    *,
    visible: set[str],
    unavailable: dict[str, str],
    denied: dict[str, str],
) -> str:
    if name in visible:
        return "visible"
    if name in unavailable:
        return "unavailable"
    if name in denied:
        return "denied"
    return "not_evaluated"
