from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from apeiria.db.engine import get_session
from apeiria.db.models.ai_persona import Persona, PersonaBinding
from apeiria.webui.auth import require_auth

router = APIRouter()


class PersonaResponse(BaseModel):
    id: int
    name: str
    prompt: str
    enabled: bool
    is_default: bool
    created_at: str
    updated_at: str


class PersonaCreate(BaseModel):
    name: str
    prompt: str
    enabled: bool = True
    is_default: bool = False


class PersonaUpdate(BaseModel):
    name: str | None = None
    prompt: str | None = None
    enabled: bool | None = None
    is_default: bool | None = None


class BindingResponse(BaseModel):
    session_id: str
    persona_id: int
    created_at: str


class BindingCreate(BaseModel):
    session_id: str
    persona_id: int


def _to_response(p: Persona) -> PersonaResponse:
    return PersonaResponse(
        id=p.id,
        name=p.name,
        prompt=p.prompt,
        enabled=bool(p.enabled),
        is_default=bool(p.is_default),
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


@router.get("", response_model=list[PersonaResponse])
async def list_personas(
    _: Annotated[Any, Depends(require_auth)],
) -> list[PersonaResponse]:
    async with get_session() as db:
        result = await db.execute(select(Persona).order_by(Persona.id))
        return [_to_response(r) for r in result.scalars()]


@router.post("", response_model=PersonaResponse, status_code=201)
async def create_persona(
    body: PersonaCreate,
    _: Annotated[Any, Depends(require_auth)],
) -> PersonaResponse:
    async with get_session() as db:
        p = Persona(
            name=body.name,
            prompt=body.prompt,
            enabled=int(body.enabled),
            is_default=int(body.is_default),
        )
        db.add(p)
        await db.commit()
        await db.refresh(p)
        return _to_response(p)


@router.get("/{persona_id}", response_model=PersonaResponse)
async def get_persona(
    persona_id: int,
    _: Annotated[Any, Depends(require_auth)],
) -> PersonaResponse:
    async with get_session() as db:
        p = await db.get(Persona, persona_id)
        if not p:
            raise HTTPException(404, "Persona not found")
        return _to_response(p)


@router.patch("/{persona_id}", response_model=PersonaResponse)
async def update_persona(
    persona_id: int,
    body: PersonaUpdate,
    _: Annotated[Any, Depends(require_auth)],
) -> PersonaResponse:
    async with get_session() as db:
        p = await db.get(Persona, persona_id)
        if not p:
            raise HTTPException(404, "Persona not found")
        for key, val in body.model_dump(exclude_unset=True).items():
            if val is None:
                continue
            if key in ("enabled", "is_default"):
                val = int(val)  # noqa: PLW2901
            setattr(p, key, val)
        await db.commit()
        await db.refresh(p)
        return _to_response(p)


@router.delete("/{persona_id}", status_code=204)
async def delete_persona(
    persona_id: int,
    _: Annotated[Any, Depends(require_auth)],
) -> None:
    async with get_session() as db:
        p = await db.get(Persona, persona_id)
        if not p:
            raise HTTPException(404, "Persona not found")
        await db.delete(p)
        await db.commit()


@router.get("/bindings/list", response_model=list[BindingResponse])
async def list_bindings(
    _: Annotated[Any, Depends(require_auth)],
) -> list[BindingResponse]:
    async with get_session() as db:
        q = select(PersonaBinding).order_by(
            PersonaBinding.created_at.desc(),
        )
        result = await db.execute(q)
        return [
            BindingResponse(
                session_id=b.session_id,
                persona_id=b.persona_id,
                created_at=b.created_at,
            )
            for b in result.scalars()
        ]


@router.post("/bindings", response_model=BindingResponse, status_code=201)
async def create_binding(
    body: BindingCreate,
    _: Annotated[Any, Depends(require_auth)],
) -> BindingResponse:
    async with get_session() as db:
        p = await db.get(Persona, body.persona_id)
        if not p:
            raise HTTPException(404, "Persona not found")
        binding = PersonaBinding(
            session_id=body.session_id,
            persona_id=body.persona_id,
        )
        db.add(binding)
        await db.commit()
        await db.refresh(binding)
        return BindingResponse(
            session_id=binding.session_id,
            persona_id=binding.persona_id,
            created_at=binding.created_at,
        )


@router.delete("/bindings/{session_id}", status_code=204)
async def delete_binding(
    session_id: str,
    _: Annotated[Any, Depends(require_auth)],
) -> None:
    async with get_session() as db:
        binding = await db.get(PersonaBinding, session_id)
        if not binding:
            raise HTTPException(404, "Binding not found")
        await db.delete(binding)
        await db.commit()
