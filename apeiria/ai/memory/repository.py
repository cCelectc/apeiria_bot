"""Async SQLAlchemy persistence for AI memory items."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, cast
from uuid import uuid4

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.sqlite import insert

from apeiria.ai.memory.models import AIMemoryDefinition
from apeiria.db.base import _epoch_ms
from apeiria.db.engine import get_session, rowcount
from apeiria.db.models.ai_memory import AIMemoryItem

if TYPE_CHECKING:
    from apeiria.ai.memory.contracts import (
        AIMemoryCreateInput,
        AIMemoryStateUpdateInput,
        AIMemoryUpdateInput,
    )
    from apeiria.ai.memory.models import (
        AIMemoryAnchorType,
        AIMemoryKind,
        AIMemoryLayer,
        AIMemoryLifecycleState,
        AIMemoryUseMode,
    )

AI_MEMORY_ACTOR_TYPES = ("system", "user", "operator", "tool")
AIMemoryActorType = str


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AIMemoryRepository:
    """Own SQL operations and row mapping for memory items."""

    async def create_memory(
        self,
        create_input: "AIMemoryCreateInput",
        *,
        ignore_existing: bool,
    ) -> AIMemoryDefinition | None:
        now = _epoch_ms()
        memory_id = f"mem_{uuid4().hex}"
        stmt = insert(AIMemoryItem).values(
            memory_id=memory_id,
            anchor_type=create_input.anchor_type,
            anchor_id=create_input.anchor_id,
            memory_layer=create_input.memory_layer,
            memory_kind=create_input.memory_kind,
            content=create_input.content,
            is_editable=1 if create_input.is_editable else 0,
            lifecycle_state=create_input.lifecycle_state,
            default_use_mode=create_input.default_use_mode,
            governance_reason=create_input.governance_reason,
            source_message_id=create_input.source_message_id,
            salience=create_input.salience,
            confidence=create_input.confidence,
            last_recalled_at=None,
            created_at=now,
        )
        if ignore_existing:
            stmt = stmt.on_conflict_do_nothing(
                index_elements=[
                    AIMemoryItem.anchor_type,
                    AIMemoryItem.anchor_id,
                    AIMemoryItem.memory_layer,
                    AIMemoryItem.memory_kind,
                    AIMemoryItem.content,
                ],
            )
        async with get_session() as session:
            result = await session.execute(stmt)
            await session.commit()
            if rowcount(result) == 0:
                return None
            row = await session.execute(
                select(AIMemoryItem).where(AIMemoryItem.memory_id == memory_id)
            )
            item = row.scalar_one()
        return _to_definition(item)

    async def get_memory_by_identity(
        self,
        create_input: "AIMemoryCreateInput",
    ) -> AIMemoryDefinition | None:
        async with get_session() as session:
            result = await session.execute(
                select(AIMemoryItem).where(
                    AIMemoryItem.anchor_type == create_input.anchor_type,
                    AIMemoryItem.anchor_id == create_input.anchor_id,
                    AIMemoryItem.memory_layer == create_input.memory_layer,
                    AIMemoryItem.memory_kind == create_input.memory_kind,
                    AIMemoryItem.content == create_input.content,
                )
            )
            item = result.scalar_one_or_none()
        if item is None:
            return None
        return _to_definition(item)

    async def get_memory(
        self,
        *,
        memory_id: str,
    ) -> AIMemoryDefinition | None:
        async with get_session() as session:
            result = await session.execute(
                select(AIMemoryItem).where(AIMemoryItem.memory_id == memory_id)
            )
            item = result.scalar_one_or_none()
        if item is None:
            return None
        return _to_definition(item)

    async def update_memory_content(
        self,
        *,
        memory_id: str,
        update_input: "AIMemoryUpdateInput",
    ) -> AIMemoryDefinition | None:
        async with get_session() as session:
            await session.execute(
                update(AIMemoryItem)
                .where(AIMemoryItem.memory_id == memory_id)
                .values(
                    content=update_input.content,
                    salience=update_input.salience,
                    confidence=update_input.confidence,
                    source_message_id=update_input.source_message_id,
                )
            )
            await session.commit()
            result = await session.execute(
                select(AIMemoryItem).where(AIMemoryItem.memory_id == memory_id)
            )
            item = result.scalar_one_or_none()
        if item is None:
            return None
        return _to_definition(item)

    async def list_memories(
        self,
        *,
        anchor_type: "AIMemoryAnchorType",
        anchor_id: str,
        memory_layer: "AIMemoryLayer | None" = None,
        memory_kind: "AIMemoryKind | None" = None,
        lifecycle_states: "tuple[AIMemoryLifecycleState, ...]" = ("active",),
    ) -> list[AIMemoryDefinition]:
        conditions = [
            AIMemoryItem.anchor_type == anchor_type,
            AIMemoryItem.anchor_id == anchor_id,
        ]
        if memory_layer is not None:
            conditions.append(AIMemoryItem.memory_layer == memory_layer)
        if memory_kind is not None:
            conditions.append(AIMemoryItem.memory_kind == memory_kind)
        if lifecycle_states:
            conditions.append(AIMemoryItem.lifecycle_state.in_(lifecycle_states))

        async with get_session() as session:
            result = await session.execute(
                select(AIMemoryItem)
                .where(*conditions)
                .order_by(AIMemoryItem.created_at.asc(), AIMemoryItem.memory_id.asc())
            )
            items = result.scalars().all()
        return [_to_definition(item) for item in items]

    async def delete_memory(
        self,
        *,
        memory_id: str,
    ) -> bool:
        async with get_session() as session:
            result = await session.execute(
                delete(AIMemoryItem).where(AIMemoryItem.memory_id == memory_id)
            )
            await session.commit()
        return (rowcount(result) or 0) > 0

    async def set_memory_state(
        self,
        *,
        memory_id: str,
        update_input: "AIMemoryStateUpdateInput",
    ) -> AIMemoryDefinition | None:
        use_mode = update_input.default_use_mode or _default_use_mode_for_state(
            update_input.lifecycle_state
        )
        async with get_session() as session:
            await session.execute(
                update(AIMemoryItem)
                .where(AIMemoryItem.memory_id == memory_id)
                .values(
                    lifecycle_state=update_input.lifecycle_state,
                    default_use_mode=use_mode,
                    governance_reason=update_input.governance_reason,
                )
            )
            await session.commit()
            result = await session.execute(
                select(AIMemoryItem).where(AIMemoryItem.memory_id == memory_id)
            )
            item = result.scalar_one_or_none()
        if item is None:
            return None
        return _to_definition(item)

    async def bulk_set_memory_state(
        self,
        *,
        memory_ids: list[str],
        update_input: "AIMemoryStateUpdateInput",
    ) -> int:
        if not memory_ids:
            return 0
        use_mode = update_input.default_use_mode or _default_use_mode_for_state(
            update_input.lifecycle_state
        )
        async with get_session() as session:
            result = await session.execute(
                update(AIMemoryItem)
                .where(AIMemoryItem.memory_id.in_(memory_ids))
                .values(
                    lifecycle_state=update_input.lifecycle_state,
                    default_use_mode=use_mode,
                    governance_reason=update_input.governance_reason,
                )
            )
            await session.commit()
        return rowcount(result) or 0

    async def mark_memories_recalled(
        self,
        *,
        memory_ids: list[str],
        recalled_at: datetime,
    ) -> None:
        if not memory_ids:
            return
        recalled_ms = int(recalled_at.timestamp() * 1000)
        async with get_session() as session:
            await session.execute(
                update(AIMemoryItem)
                .where(AIMemoryItem.memory_id.in_(memory_ids))
                .values(last_recalled_at=recalled_ms)
            )
            await session.commit()


def _to_definition(item: AIMemoryItem) -> AIMemoryDefinition:
    return AIMemoryDefinition(
        memory_id=item.memory_id,
        anchor_type=cast("AIMemoryAnchorType", item.anchor_type),
        anchor_id=item.anchor_id,
        memory_layer=cast("AIMemoryLayer", item.memory_layer),
        memory_kind=cast("AIMemoryKind", item.memory_kind),
        content=item.content,
        is_editable=bool(item.is_editable),
        lifecycle_state=cast("AIMemoryLifecycleState", item.lifecycle_state),
        default_use_mode=cast("AIMemoryUseMode", item.default_use_mode),
        governance_reason=item.governance_reason,
        source_message_id=item.source_message_id,
        salience=item.salience,
        confidence=item.confidence,
        last_recalled_at=_epoch_ms_to_datetime(item.last_recalled_at)
        if item.last_recalled_at is not None
        else None,
        created_at=_epoch_ms_to_datetime(item.created_at),
    )


def _default_use_mode_for_state(state: str) -> str:
    return "context" if state == "active" else "ignore"


def _epoch_ms_to_datetime(ms: int | str) -> datetime:
    return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc)
