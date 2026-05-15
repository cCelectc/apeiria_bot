"""AI memory admin routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query

from apeiria.app.ai import ai_application
from apeiria.webui.auth import require_control_panel

from .memories_schemas import (
    AIMemoryBulkActionRequest,
    AIMemoryBulkActionResult,
    AIMemoryBulkLifecycleRequest,
    AIMemoryCreateRequest,
    AIMemoryDeleteResult,
    AIMemoryItem,
    AIMemoryLifecycleRequest,
    AIMemoryUpdateRequest,
    to_ai_memory_item,
)

if TYPE_CHECKING:
    from apeiria.access.principal import AuthSession


router = APIRouter()


def _actor_username_from_claims(session: "AuthSession") -> str | None:
    username = session.username.strip()
    return username or None


@router.get("/memories", response_model=list[AIMemoryItem])
async def list_ai_memories(  # noqa: PLR0913
    _: Annotated[Any, Depends(require_control_panel)],
    anchor_type: Annotated[
        Literal["scene", "participant", "user"],
        Query(),
    ],
    anchor_id: Annotated[str, Query(min_length=1)],
    query: str = "",
    memory_layer: Annotated[str | None, Query(max_length=32)] = None,
    memory_kind: Annotated[str | None, Query(max_length=32)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[AIMemoryItem]:
    memories = await ai_application.operations.list_memories(
        anchor_type=anchor_type,
        anchor_id=anchor_id,
        query_text=query,
        memory_layer=memory_layer,
        memory_kind=memory_kind,
        limit=limit,
    )
    return [to_ai_memory_item(item) for item in memories]


@router.post("/memories", response_model=AIMemoryItem)
async def create_ai_memory(
    payload: AIMemoryCreateRequest,
    session: Annotated["AuthSession", Depends(require_control_panel)],
) -> AIMemoryItem:
    memory = await ai_application.operations.create_memory(
        memory_layer=payload.memory_layer,
        memory_kind=payload.memory_kind,
        anchor_type=payload.anchor_type,
        anchor_id=payload.anchor_id,
        content=payload.content,
        salience=payload.salience,
        confidence=payload.confidence,
        actor_username=_actor_username_from_claims(session),
    )
    return to_ai_memory_item(memory)


@router.patch("/memories", response_model=AIMemoryItem | None)
async def update_ai_memory(
    payload: AIMemoryUpdateRequest,
    session: Annotated["AuthSession", Depends(require_control_panel)],
) -> AIMemoryItem | None:
    memory = await ai_application.operations.update_memory(
        memory_id=payload.memory_id,
        content=payload.content,
        salience=payload.salience,
        confidence=payload.confidence,
        actor_username=_actor_username_from_claims(session),
    )
    return to_ai_memory_item(memory) if memory is not None else None


@router.delete("/memories", response_model=AIMemoryDeleteResult)
async def delete_ai_memory(
    session: Annotated["AuthSession", Depends(require_control_panel)],
    memory_id: Annotated[str, Query(min_length=1)],
) -> AIMemoryDeleteResult:
    return AIMemoryDeleteResult(
        deleted=await ai_application.operations.delete_memory(
            memory_id=memory_id,
            actor_username=_actor_username_from_claims(session),
        )
    )


@router.patch("/memories/lifecycle", response_model=AIMemoryItem | None)
async def set_ai_memory_lifecycle(
    payload: AIMemoryLifecycleRequest,
    session: Annotated["AuthSession", Depends(require_control_panel)],
) -> AIMemoryItem | None:
    memory = await ai_application.operations.set_memory_lifecycle(
        memory_id=payload.memory_id,
        lifecycle_state=payload.lifecycle_state,
        actor_username=_actor_username_from_claims(session),
    )
    return to_ai_memory_item(memory) if memory is not None else None


@router.post("/memories/bulk-delete", response_model=AIMemoryBulkActionResult)
async def bulk_delete_ai_memories(
    payload: AIMemoryBulkActionRequest,
    session: Annotated["AuthSession", Depends(require_control_panel)],
) -> AIMemoryBulkActionResult:
    count = await ai_application.operations.bulk_delete_memories(
        memory_ids=payload.memory_ids,
        actor_username=_actor_username_from_claims(session),
    )
    return AIMemoryBulkActionResult(affected=count)


@router.post("/memories/bulk-lifecycle", response_model=AIMemoryBulkActionResult)
async def bulk_set_ai_memory_lifecycle(
    payload: AIMemoryBulkLifecycleRequest,
    session: Annotated["AuthSession", Depends(require_control_panel)],
) -> AIMemoryBulkActionResult:
    count = await ai_application.operations.bulk_set_memory_lifecycle(
        memory_ids=payload.memory_ids,
        lifecycle_state=payload.lifecycle_state,
        actor_username=_actor_username_from_claims(session),
    )
    return AIMemoryBulkActionResult(affected=count)


__all__ = ["router"]
