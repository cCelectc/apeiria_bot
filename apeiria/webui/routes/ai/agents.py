from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from apeiria.db.engine import get_session
from apeiria.db.models.infrastructure import ACPAgent
from apeiria.webui.auth import require_auth

router = APIRouter()


class AgentResponse(BaseModel):
    id: int
    name: str
    command: str
    args_json: str | None
    env_json: str | None
    workspace: str | None
    enabled: bool
    created_at: str
    updated_at: str


class AgentCreate(BaseModel):
    name: str
    command: str
    args_json: str | None = None
    env_json: str | None = None
    workspace: str | None = None
    enabled: bool = True


class AgentUpdate(BaseModel):
    name: str | None = None
    command: str | None = None
    args_json: str | None = None
    env_json: str | None = None
    workspace: str | None = None
    enabled: bool | None = None


def _to_response(a: ACPAgent) -> AgentResponse:
    return AgentResponse(
        id=a.id,
        name=a.name,
        command=a.command,
        args_json=a.args_json,
        env_json=a.env_json,
        workspace=a.workspace,
        enabled=bool(a.enabled),
        created_at=a.created_at,
        updated_at=a.updated_at,
    )


@router.get("", response_model=list[AgentResponse])
async def list_agents(
    _: Annotated[Any, Depends(require_auth)],
) -> list[AgentResponse]:
    async with get_session() as db:
        result = await db.execute(select(ACPAgent).order_by(ACPAgent.id))
        return [_to_response(r) for r in result.scalars()]


@router.post("", response_model=AgentResponse, status_code=201)
async def create_agent(
    body: AgentCreate,
    _: Annotated[Any, Depends(require_auth)],
) -> AgentResponse:
    async with get_session() as db:
        agent = ACPAgent(
            name=body.name,
            command=body.command,
            args_json=body.args_json,
            env_json=body.env_json,
            workspace=body.workspace,
            enabled=int(body.enabled),
        )
        db.add(agent)
        await db.commit()
        await db.refresh(agent)
        return _to_response(agent)


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: int,
    _: Annotated[Any, Depends(require_auth)],
) -> AgentResponse:
    async with get_session() as db:
        agent = await db.get(ACPAgent, agent_id)
        if not agent:
            raise HTTPException(404, "Agent not found")
        return _to_response(agent)


@router.patch("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: int,
    body: AgentUpdate,
    _: Annotated[Any, Depends(require_auth)],
) -> AgentResponse:
    async with get_session() as db:
        agent = await db.get(ACPAgent, agent_id)
        if not agent:
            raise HTTPException(404, "Agent not found")
        for key, val in body.model_dump(exclude_unset=True).items():
            if val is None:
                continue
            if key == "enabled":
                val = int(val)  # noqa: PLW2901
            setattr(agent, key, val)
        await db.commit()
        await db.refresh(agent)
        return _to_response(agent)


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(
    agent_id: int,
    _: Annotated[Any, Depends(require_auth)],
) -> None:
    async with get_session() as db:
        agent = await db.get(ACPAgent, agent_id)
        if not agent:
            raise HTTPException(404, "Agent not found")
        await db.delete(agent)
        await db.commit()
