from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from apeiria.ai.tools.registry import ToolRegistry
from apeiria.webui.auth import require_auth

router = APIRouter()


class ToolResponse(BaseModel):
    name: str
    description: str
    required_level: str
    enabled: bool
    origin: str
    parameters_schema: dict | None


@router.get("", response_model=list[ToolResponse])
async def list_tools(
    _: Annotated[Any, Depends(require_auth)],
) -> list[ToolResponse]:
    tools = ToolRegistry.list_all()
    return [
        ToolResponse(
            name=t.name,
            description=t.description,
            required_level=getattr(t, "required_level", "everyone"),
            enabled=getattr(t, "enabled", True),
            origin=getattr(t, "origin", "unknown"),
            parameters_schema=t.parameters,
        )
        for t in tools
    ]
