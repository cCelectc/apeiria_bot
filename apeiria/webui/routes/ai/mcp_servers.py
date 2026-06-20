from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from apeiria.db.engine import get_session
from apeiria.db.models.infrastructure import MCPServer
from apeiria.webui.auth import require_auth

router = APIRouter()


class MCPServerResponse(BaseModel):
    id: int
    name: str
    transport: str
    command: str | None
    args_json: str | None
    env_json: str | None
    url: str | None
    headers_json: str | None
    enabled: bool
    created_at: str
    updated_at: str


class MCPServerCreate(BaseModel):
    name: str
    transport: str
    command: str | None = None
    args_json: str | None = None
    env_json: str | None = None
    url: str | None = None
    headers_json: str | None = None
    enabled: bool = True


class MCPServerUpdate(BaseModel):
    name: str | None = None
    transport: str | None = None
    command: str | None = None
    args_json: str | None = None
    env_json: str | None = None
    url: str | None = None
    headers_json: str | None = None
    enabled: bool | None = None


def _to_response(s: MCPServer) -> MCPServerResponse:
    return MCPServerResponse(
        id=s.id,
        name=s.name,
        transport=s.transport,
        command=s.command,
        args_json=s.args_json,
        env_json=s.env_json,
        url=s.url,
        headers_json=s.headers_json,
        enabled=bool(s.enabled),
        created_at=s.created_at,
        updated_at=s.updated_at,
    )


@router.get("", response_model=list[MCPServerResponse])
async def list_servers(
    _: Annotated[Any, Depends(require_auth)],
) -> list[MCPServerResponse]:
    async with get_session() as db:
        result = await db.execute(select(MCPServer).order_by(MCPServer.id))
        return [_to_response(r) for r in result.scalars()]


@router.post("", response_model=MCPServerResponse, status_code=201)
async def create_server(
    body: MCPServerCreate,
    _: Annotated[Any, Depends(require_auth)],
) -> MCPServerResponse:
    async with get_session() as db:
        srv = MCPServer(
            name=body.name,
            transport=body.transport,
            command=body.command,
            args_json=body.args_json,
            env_json=body.env_json,
            url=body.url,
            headers_json=body.headers_json,
            enabled=int(body.enabled),
        )
        db.add(srv)
        await db.commit()
        await db.refresh(srv)
        return _to_response(srv)


@router.get("/{server_id}", response_model=MCPServerResponse)
async def get_server(
    server_id: int,
    _: Annotated[Any, Depends(require_auth)],
) -> MCPServerResponse:
    async with get_session() as db:
        srv = await db.get(MCPServer, server_id)
        if not srv:
            raise HTTPException(404, "MCP server not found")
        return _to_response(srv)


@router.patch("/{server_id}", response_model=MCPServerResponse)
async def update_server(
    server_id: int,
    body: MCPServerUpdate,
    _: Annotated[Any, Depends(require_auth)],
) -> MCPServerResponse:
    async with get_session() as db:
        srv = await db.get(MCPServer, server_id)
        if not srv:
            raise HTTPException(404, "MCP server not found")
        for key, val in body.model_dump(exclude_unset=True).items():
            if val is None:
                continue
            if key == "enabled":
                val = int(val)  # noqa: PLW2901
            setattr(srv, key, val)
        await db.commit()
        await db.refresh(srv)
        return _to_response(srv)


@router.delete("/{server_id}", status_code=204)
async def delete_server(
    server_id: int,
    _: Annotated[Any, Depends(require_auth)],
) -> None:
    async with get_session() as db:
        srv = await db.get(MCPServer, server_id)
        if not srv:
            raise HTTPException(404, "MCP server not found")
        await db.delete(srv)
        await db.commit()
