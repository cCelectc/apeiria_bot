"""SQLite-backed persistence for AI memory items."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Literal, cast
from uuid import uuid4

from apeiria.ai.memory.models import AIMemoryDefinition
from apeiria.db.runtime import database_runtime

if TYPE_CHECKING:
    from sqlite3 import Connection

    from apeiria.ai.memory.contracts import (
        AIMemoryCreateInput,
        AIMemoryStateUpdateInput,
        AIMemoryUpdateInput,
    )
    from apeiria.ai.memory.models import (
        AIMemoryAnchorType,
        AIMemoryBeliefAction,
        AIMemoryKind,
        AIMemoryLayer,
        AIMemoryLifecycleState,
        AIMemoryUseMode,
    )

AI_MEMORY_ACTOR_TYPES = ("system", "user", "operator", "tool")
AIMemoryActorType = Literal["system", "user", "operator", "tool"]


@dataclass
class _MemoryRow:
    id: int
    memory_id: str
    anchor_type: str
    anchor_id: str
    memory_layer: str
    memory_kind: str
    content: str
    is_editable: bool
    lifecycle_state: str
    default_use_mode: str
    governance_reason: str | None
    source_message_id: str | None
    salience: float
    confidence: float
    last_recalled_at: datetime | None
    created_at: datetime


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AIMemoryRepository:
    """Own SQL operations and row mapping for memory items."""

    def create_memory(
        self,
        create_input: AIMemoryCreateInput,
        *,
        ignore_existing: bool,
    ) -> AIMemoryDefinition | None:
        with database_runtime.transaction_sync() as connection:
            row = _insert_memory_row(
                connection,
                create_input,
                ignore_existing=ignore_existing,
            )
        if row is None:
            return None
        return _to_definition(row)

    def get_memory_by_identity(
        self,
        create_input: AIMemoryCreateInput,
    ) -> AIMemoryDefinition | None:
        with database_runtime.connect_sync() as connection:
            row = connection.execute(
                _SELECT_MEMORY_FIELDS
                + """
                WHERE
                    anchor_type = ?
                    AND anchor_id = ?
                    AND memory_layer = ?
                    AND memory_kind = ?
                    AND content = ?
                """,
                (
                    create_input.anchor_type,
                    create_input.anchor_id,
                    create_input.memory_layer,
                    create_input.memory_kind,
                    create_input.content,
                ),
            ).fetchone()
        if row is None:
            return None
        return _to_definition(_row_to_memory(row))

    def get_memory(
        self,
        *,
        memory_id: str,
    ) -> AIMemoryDefinition | None:
        row = _get_memory_row(memory_id=memory_id)
        if row is None:
            return None
        return _to_definition(row)

    def update_memory_content(
        self,
        *,
        memory_id: str,
        update_input: AIMemoryUpdateInput,
    ) -> AIMemoryDefinition | None:
        row = _get_memory_row(memory_id=memory_id)
        if row is None:
            return None
        row.content = update_input.content
        row.salience = update_input.salience
        row.confidence = update_input.confidence
        row.source_message_id = update_input.source_message_id
        with database_runtime.connect_sync() as connection:
            connection.execute(
                """
                UPDATE ai_memory_item
                SET
                    content = ?,
                    salience = ?,
                    confidence = ?,
                    source_message_id = ?
                WHERE memory_id = ?
                """,
                (
                    row.content,
                    row.salience,
                    row.confidence,
                    row.source_message_id,
                    memory_id,
                ),
            )
        return _to_definition(row)

    def list_memories(
        self,
        *,
        anchor_type: AIMemoryAnchorType,
        anchor_id: str,
        memory_layer: AIMemoryLayer | None = None,
        memory_kind: AIMemoryKind | None = None,
        lifecycle_states: tuple[AIMemoryLifecycleState, ...] = ("active",),
    ) -> list[AIMemoryDefinition]:
        conditions = ["anchor_type = ?", "anchor_id = ?"]
        params: list[object] = [anchor_type, anchor_id]
        if memory_layer is not None:
            conditions.append("memory_layer = ?")
            params.append(memory_layer)
        if memory_kind is not None:
            conditions.append("memory_kind = ?")
            params.append(memory_kind)
        if lifecycle_states:
            placeholders = ",".join("?" for _ in lifecycle_states)
            conditions.append(f"lifecycle_state IN ({placeholders})")
            params.extend(lifecycle_states)

        with database_runtime.connect_sync() as connection:
            rows = connection.execute(
                _SELECT_MEMORY_FIELDS
                + f"""
                WHERE {" AND ".join(conditions)}
                ORDER BY created_at ASC, id ASC
                """,
                tuple(params),
            ).fetchall()
        return [_to_definition(_row_to_memory(row)) for row in rows]

    def delete_memory(
        self,
        *,
        memory_id: str,
    ) -> bool:
        with database_runtime.connect_sync() as connection:
            cursor = connection.execute(
                "DELETE FROM ai_memory_item WHERE memory_id = ?",
                (memory_id,),
            )
        return int(cursor.rowcount or 0) > 0

    def set_memory_state(
        self,
        *,
        memory_id: str,
        update_input: AIMemoryStateUpdateInput,
    ) -> AIMemoryDefinition | None:
        row = _get_memory_row(memory_id=memory_id)
        if row is None:
            return None
        row.lifecycle_state = update_input.lifecycle_state
        if update_input.default_use_mode is not None:
            row.default_use_mode = update_input.default_use_mode
        row.governance_reason = update_input.governance_reason
        with database_runtime.connect_sync() as connection:
            connection.execute(
                """
                UPDATE ai_memory_item
                SET
                    lifecycle_state = ?,
                    default_use_mode = ?,
                    governance_reason = ?
                WHERE memory_id = ?
                """,
                (
                    row.lifecycle_state,
                    row.default_use_mode,
                    row.governance_reason,
                    memory_id,
                ),
            )
        return _to_definition(row)

    def bulk_set_memory_state(
        self,
        *,
        memory_ids: list[str],
        update_input: AIMemoryStateUpdateInput,
    ) -> int:
        if not memory_ids:
            return 0
        placeholders = ",".join("?" for _ in memory_ids)
        with database_runtime.connect_sync() as connection:
            cursor = connection.execute(
                f"""
                UPDATE ai_memory_item
                SET
                    lifecycle_state = ?,
                    default_use_mode = ?,
                    governance_reason = ?
                WHERE memory_id IN ({placeholders})
                """,
                (
                    update_input.lifecycle_state,
                    update_input.default_use_mode
                    or _default_use_mode_for_state(update_input.lifecycle_state),
                    update_input.governance_reason,
                    *memory_ids,
                ),
            )
        return int(cursor.rowcount or 0)

    def record_belief_action(  # noqa: PLR0913
        self,
        *,
        memory_id: str | None,
        action: AIMemoryBeliefAction,
        actor_type: AIMemoryActorType,
        reason: str | None = None,
        source_message_id: str | None = None,
        previous_state: AIMemoryLifecycleState | None = None,
        next_state: AIMemoryLifecycleState | None = None,
    ) -> None:
        with database_runtime.connect_sync() as connection:
            connection.execute(
                """
                INSERT INTO ai_memory_belief_action (
                    action_id,
                    memory_id,
                    action,
                    actor_type,
                    reason,
                    source_message_id,
                    previous_state,
                    next_state,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"mem_action_{uuid4().hex}",
                    memory_id,
                    action,
                    actor_type,
                    reason,
                    source_message_id,
                    previous_state,
                    next_state,
                    _datetime_to_text(utcnow()),
                ),
            )

    def mark_memories_recalled(
        self,
        *,
        memory_ids: list[str],
        recalled_at: datetime,
    ) -> None:
        if not memory_ids:
            return

        placeholders = ",".join("?" for _ in memory_ids)
        with database_runtime.connect_sync() as connection:
            connection.execute(
                f"""
                UPDATE ai_memory_item
                SET last_recalled_at = ?
                WHERE memory_id IN ({placeholders})
                """,
                (_datetime_to_text(recalled_at), *memory_ids),
            )


def _insert_memory_row(
    connection: "Connection",
    create_input: AIMemoryCreateInput,
    *,
    ignore_existing: bool,
) -> _MemoryRow | None:
    now = utcnow()
    memory_id = f"mem_{uuid4().hex}"
    conflict_clause = (
        """
        ON CONFLICT(anchor_type, anchor_id, memory_layer, memory_kind, content)
        DO NOTHING
        """
        if ignore_existing
        else ""
    )
    cursor = connection.execute(
        f"""
        INSERT INTO ai_memory_item (
            memory_id,
            anchor_type,
            anchor_id,
            memory_layer,
            memory_kind,
            content,
            is_editable,
            lifecycle_state,
            default_use_mode,
            governance_reason,
            source_message_id,
            salience,
            confidence,
            last_recalled_at,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        {conflict_clause}
        """,
        (
            memory_id,
            create_input.anchor_type,
            create_input.anchor_id,
            create_input.memory_layer,
            create_input.memory_kind,
            create_input.content,
            1 if create_input.is_editable else 0,
            create_input.lifecycle_state,
            create_input.default_use_mode,
            create_input.governance_reason,
            create_input.source_message_id,
            create_input.salience,
            create_input.confidence,
            None,
            _datetime_to_text(now),
        ),
    )
    if cursor.rowcount == 0:
        return None
    return _MemoryRow(
        id=int(cursor.lastrowid or 0),
        memory_id=memory_id,
        anchor_type=create_input.anchor_type,
        anchor_id=create_input.anchor_id,
        memory_layer=create_input.memory_layer,
        memory_kind=create_input.memory_kind,
        content=create_input.content,
        is_editable=create_input.is_editable,
        lifecycle_state=create_input.lifecycle_state,
        default_use_mode=create_input.default_use_mode,
        governance_reason=create_input.governance_reason,
        source_message_id=create_input.source_message_id,
        salience=create_input.salience,
        confidence=create_input.confidence,
        last_recalled_at=None,
        created_at=now,
    )


def _get_memory_row(*, memory_id: str) -> _MemoryRow | None:
    with database_runtime.connect_sync() as connection:
        row = connection.execute(
            _SELECT_MEMORY_FIELDS + " WHERE memory_id = ?",
            (memory_id,),
        ).fetchone()
    return None if row is None else _row_to_memory(row)


def _to_definition(row: _MemoryRow) -> AIMemoryDefinition:
    return AIMemoryDefinition(
        memory_id=row.memory_id,
        anchor_type=cast("AIMemoryAnchorType", row.anchor_type),
        anchor_id=row.anchor_id,
        memory_layer=cast("AIMemoryLayer", row.memory_layer),
        memory_kind=cast("AIMemoryKind", row.memory_kind),
        content=row.content,
        is_editable=row.is_editable,
        lifecycle_state=cast("AIMemoryLifecycleState", row.lifecycle_state),
        default_use_mode=cast("AIMemoryUseMode", row.default_use_mode),
        governance_reason=row.governance_reason,
        source_message_id=row.source_message_id,
        salience=row.salience,
        confidence=row.confidence,
        last_recalled_at=row.last_recalled_at,
        created_at=row.created_at,
    )


_SELECT_MEMORY_FIELDS = """
SELECT
    id,
    memory_id,
    anchor_type,
    anchor_id,
    memory_layer,
    memory_kind,
    content,
    is_editable,
    lifecycle_state,
    default_use_mode,
    governance_reason,
    source_message_id,
    salience,
    confidence,
    last_recalled_at,
    created_at
FROM ai_memory_item
"""


def _row_to_memory(row: tuple[object, ...]) -> _MemoryRow:
    return _MemoryRow(
        id=int(str(row[0])),
        memory_id=str(row[1]),
        anchor_type=str(row[2]),
        anchor_id=str(row[3]),
        memory_layer=str(row[4]),
        memory_kind=str(row[5]),
        content=str(row[6]),
        is_editable=bool(row[7]),
        lifecycle_state=str(row[8]),
        default_use_mode=str(row[9]),
        governance_reason=str(row[10]) if row[10] is not None else None,
        source_message_id=str(row[11]) if row[11] is not None else None,
        salience=float(str(row[12])),
        confidence=float(str(row[13])),
        last_recalled_at=_optional_datetime_from_text(row[14]),
        created_at=_datetime_from_text(row[15]),
    )


def _default_use_mode_for_state(state: str) -> str:
    return "context" if state == "active" else "ignore"


def _datetime_to_text(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def _datetime_from_text(value: object) -> datetime:
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _optional_datetime_from_text(value: object | None) -> datetime | None:
    return None if value is None else _datetime_from_text(value)
