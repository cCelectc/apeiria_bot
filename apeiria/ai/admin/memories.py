"""Memory admin operations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, cast

from apeiria.ai.admin.audit import record_ai_admin_audit
from apeiria.ai.memory.service import (
    AIMemoryCreateInput,
    AIMemoryQuery,
    AIMemoryUpdateInput,
    ai_memory_service,
)

if TYPE_CHECKING:
    from apeiria.ai.memory.models import (
        AIMemoryAnchorType,
        AIMemoryDefinition,
        AIMemoryKind,
        AIMemoryLayer,
    )


def _normalize_memory_anchor_type(
    anchor_type: str,
) -> Literal["scene", "participant", "user"]:
    if anchor_type in {"scene", "participant", "user"}:
        return cast("Literal['scene', 'participant', 'user']", anchor_type)
    msg = f"Unsupported memory anchor_type: {anchor_type}"
    raise ValueError(msg)


def _normalize_optional_memory_layer(
    memory_layer: str | None,
) -> Literal["summary", "long_term", "knowledge", "operator"] | None:
    if memory_layer in {"summary", "long_term", "knowledge", "operator"}:
        return cast(
            "Literal['summary', 'long_term', 'knowledge', 'operator']",
            memory_layer,
        )
    return None


def _normalize_optional_memory_kind(
    memory_kind: str | None,
) -> Literal["fact", "preference", "relationship", "note"] | None:
    if memory_kind in {"fact", "preference", "relationship", "note"}:
        return cast(
            "Literal['fact', 'preference', 'relationship', 'note']",
            memory_kind,
        )
    return None


def _normalize_required_memory_layer(
    memory_layer: str,
) -> Literal["summary", "long_term", "knowledge", "operator"]:
    normalized_layer = _normalize_optional_memory_layer(memory_layer)
    if normalized_layer is not None:
        return normalized_layer
    msg = f"Unsupported memory layer: {memory_layer}"
    raise ValueError(msg)


def _normalize_required_memory_kind(
    memory_kind: str,
) -> Literal["fact", "preference", "relationship", "note"]:
    normalized_kind = _normalize_optional_memory_kind(memory_kind)
    if normalized_kind is not None:
        return normalized_kind
    msg = f"Unsupported memory kind: {memory_kind}"
    raise ValueError(msg)


class MemoriesAdminMixin:
    """Admin CRUD, bulk ops, and ignored-toggle for AI memory items."""

    async def list_memories(  # noqa: PLR0913
        self,
        *,
        anchor_type: str,
        anchor_id: str,
        query_text: str = "",
        limit: int = 20,
        memory_layer: str | None = None,
        memory_kind: str | None = None,
    ) -> list["AIMemoryDefinition"]:
        normalized_layer = _normalize_optional_memory_layer(memory_layer)
        normalized_kind = _normalize_optional_memory_kind(memory_kind)
        normalized_anchor_type = _normalize_memory_anchor_type(anchor_type)
        if query_text.strip():
            return await ai_memory_service.retrieve_memories(
                AIMemoryQuery(
                    anchor_type=normalized_anchor_type,
                    anchor_id=anchor_id,
                    query_text=query_text,
                    limit=limit,
                    memory_layer=normalized_layer,
                    memory_kind=normalized_kind,
                ),
            )
        memories = await ai_memory_service.list_memories(
            anchor_type=normalized_anchor_type,
            anchor_id=anchor_id,
            memory_layer=normalized_layer,
            memory_kind=normalized_kind,
            include_ignored=True,
        )
        return memories[:limit]

    async def create_memory(  # noqa: PLR0913
        self,
        *,
        memory_layer: str,
        memory_kind: str,
        anchor_type: str,
        anchor_id: str,
        content: str,
        salience: float,
        confidence: float,
        actor_username: str | None = None,
    ) -> "AIMemoryDefinition":
        normalized_layer = cast(
            "AIMemoryLayer",
            _normalize_required_memory_layer(memory_layer),
        )
        normalized_kind = cast(
            "AIMemoryKind",
            _normalize_required_memory_kind(memory_kind),
        )
        normalized_anchor_type = _normalize_memory_anchor_type(anchor_type)
        create_input = AIMemoryCreateInput(
            anchor_type=normalized_anchor_type,
            anchor_id=anchor_id,
            memory_layer=normalized_layer,
            memory_kind=normalized_kind,
            content=content,
            is_editable=(normalized_layer != "summary"),
            salience=salience,
            confidence=confidence,
        )
        if normalized_layer == "summary":
            msg = "summary memories are system-managed and cannot be created manually"
            raise ValueError(msg)
        if normalized_layer == "knowledge":
            row = await ai_memory_service.create_knowledge_memory(create_input)
        else:
            row = await ai_memory_service.create_memory_if_absent(create_input)
            if row is None:
                existing = await ai_memory_service.get_memory_by_identity(
                    create_input,
                )
                assert existing is not None
                row = existing
        memories = await ai_memory_service.list_memories(
            anchor_type=normalized_anchor_type,
            anchor_id=anchor_id,
            memory_layer=normalized_layer,
            include_ignored=True,
        )
        created = next(item for item in memories if item.memory_id == row.memory_id)
        record_ai_admin_audit(
            "ai_memory_created",
            actor_username=actor_username,
            detail=f"{created.memory_id} {created.anchor_type}:{created.anchor_id}",
        )
        return created

    async def delete_memory(
        self,
        *,
        memory_id: str,
        actor_username: str | None = None,
    ) -> bool:
        existing = await ai_memory_service.get_memory(memory_id=memory_id)
        deleted = await ai_memory_service.delete_memory(
            memory_id=memory_id,
        )
        if deleted:
            record_ai_admin_audit(
                "ai_memory_deleted",
                actor_username=actor_username,
                detail=(
                    f"{memory_id} {existing.anchor_type}:{existing.anchor_id}"
                    if existing is not None
                    else memory_id
                ),
            )
        return deleted

    async def update_memory(
        self,
        *,
        memory_id: str,
        content: str,
        salience: float,
        confidence: float,
        actor_username: str | None = None,
    ) -> "AIMemoryDefinition | None":
        existing = await ai_memory_service.get_memory(memory_id=memory_id)
        if existing is None:
            return None
        if not existing.is_editable or existing.memory_layer == "summary":
            return None
        row = await ai_memory_service.update_memory_content(
            memory_id=memory_id,
            update_input=AIMemoryUpdateInput(
                content=content,
                salience=salience,
                confidence=confidence,
                source_message_id=None,
            ),
        )
        if row is None:
            return None
        if row.memory_layer == "knowledge":
            await ai_memory_service.upsert_memory_embedding(
                memory_id=row.memory_id,
                content=row.content,
            )
        memories = await ai_memory_service.list_memories(
            anchor_type=cast("AIMemoryAnchorType", row.anchor_type),
            anchor_id=row.anchor_id,
            memory_layer=cast("AIMemoryLayer", row.memory_layer),
            include_ignored=True,
        )
        updated = next(
            (item for item in memories if item.memory_id == row.memory_id),
        )
        if updated is not None:
            record_ai_admin_audit(
                "ai_memory_updated",
                actor_username=actor_username,
                detail=f"{updated.memory_id} {updated.anchor_type}:{updated.anchor_id}",
            )
        return updated

    async def toggle_memory_ignored(
        self,
        *,
        memory_id: str,
        actor_username: str | None = None,
    ) -> "AIMemoryDefinition | None":
        result = await ai_memory_service.toggle_memory_ignored(
            memory_id=memory_id,
        )
        if result is not None:
            record_ai_admin_audit(
                "ai_memory_ignored_toggled",
                actor_username=actor_username,
                detail=f"{result.memory_id} ignored={result.is_ignored}",
            )
        return result

    async def bulk_delete_memories(
        self,
        *,
        memory_ids: list[str],
        actor_username: str | None = None,
    ) -> int:
        count = await ai_memory_service.bulk_delete_memories(
            memory_ids=memory_ids,
        )
        if count > 0:
            record_ai_admin_audit(
                "ai_memory_bulk_deleted",
                actor_username=actor_username,
                detail=f"count={count}",
            )
        return count

    async def bulk_set_memories_ignored(
        self,
        *,
        memory_ids: list[str],
        ignored: bool,
        actor_username: str | None = None,
    ) -> int:
        count = await ai_memory_service.bulk_set_ignored(
            memory_ids=memory_ids,
            ignored=ignored,
        )
        if count > 0:
            record_ai_admin_audit(
                "ai_memory_bulk_ignored_set",
                actor_username=actor_username,
                detail=f"count={count} ignored={ignored}",
            )
        return count


__all__ = ["MemoriesAdminMixin"]
