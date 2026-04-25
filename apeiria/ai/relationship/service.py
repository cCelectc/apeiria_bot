"""Relationship state storage and emotion projection service."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, cast
from uuid import uuid4

from apeiria.ai.relationship.models import (
    AIRelationshipDelta,
    AIRelationshipEvent,
    AIRelationshipEventType,
    AIRelationshipState,
    EmotionProjection,
)
from apeiria.ai.relationship.scope import build_affinity_scope_key
from apeiria.ai.relationship.scoring import (
    apply_inactivity_decay,
    apply_relationship_delta,
    project_emotion,
)
from apeiria.db.runtime import database_runtime

if TYPE_CHECKING:
    from sqlite3 import Connection


@dataclass
class _AffinityRow:
    id: int
    affinity_id: str
    platform: str
    group_id: str | None
    scope_key: str
    user_id: str
    score: float
    mood_tags_json: str
    last_event_at: datetime
    last_decay_at: datetime | None


@dataclass(frozen=True)
class _RelationshipEventRow:
    id: int
    event_id: str
    affinity_id: str
    platform: str
    group_id: str | None
    user_id: str
    event_type: str
    score_delta: float
    score_after: float
    mood_tag: str | None
    reason: str | None
    created_at: datetime


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


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


class AIRelationshipService:
    """Relationship persistence and emotion projection service."""

    async def get_state_snapshot(
        self,
        *,
        platform: str,
        group_id: str | None,
        user_id: str,
    ) -> tuple[float, tuple[str, ...]]:
        """Return a compact relationship snapshot for adjacent prompt systems."""
        state = await self.get_effective_state(
            platform=platform,
            group_id=group_id,
            user_id=user_id,
        )
        return state.score, state.mood_tags

    async def get_state(
        self,
        *,
        platform: str,
        group_id: str | None,
        user_id: str,
    ) -> AIRelationshipState:
        """Load or initialize relationship state."""
        row = self._find_row(
            platform=platform,
            group_id=group_id,
            user_id=user_id,
        )
        if row is None:
            return self._build_default_state(
                platform=platform,
                group_id=group_id,
                user_id=user_id,
            )
        return self._to_state(row)

    async def get_effective_state(
        self,
        *,
        platform: str,
        group_id: str | None,
        user_id: str,
    ) -> AIRelationshipState:
        """Load one relationship state with read-time decay applied in memory."""
        row = self._find_row(
            platform=platform,
            group_id=group_id,
            user_id=user_id,
        )
        if row is None:
            return self._build_default_state(
                platform=platform,
                group_id=group_id,
                user_id=user_id,
            )
        return self._build_effective_state(row)

    async def apply_delta(
        self,
        *,
        platform: str,
        group_id: str | None,
        user_id: str,
        delta: AIRelationshipDelta,
    ) -> AIRelationshipState:
        """Apply one deterministic delta and persist the updated state."""
        with database_runtime.transaction_sync() as connection:
            row = self._get_or_create_row(
                connection,
                platform=platform,
                group_id=group_id,
                user_id=user_id,
            )
            state = self._persist_inactivity_decay(connection, row)

            updated = apply_relationship_delta(state, delta)
            now = _utcnow()
            row.score = updated.score
            row.mood_tags_json = self._serialize_mood_tags(updated.mood_tags)
            row.last_event_at = now
            row.last_decay_at = None
            self._update_row(connection, row)
            self._record_event(
                connection,
                affinity_id=row.affinity_id,
                platform=row.platform,
                group_id=row.group_id,
                user_id=row.user_id,
                event_type=delta.event_type,
                score_delta=updated.score - state.score,
                score_after=updated.score,
                mood_tag=delta.mood_tag,
                reason=delta.reason,
                created_at=now,
            )
        return self._to_state(row)

    async def set_manual_score(
        self,
        *,
        platform: str,
        group_id: str | None,
        user_id: str,
        score: float,
    ) -> AIRelationshipState:
        """Persist an operator override for relationship score."""
        with database_runtime.transaction_sync() as connection:
            row = self._get_or_create_row(
                connection,
                platform=platform,
                group_id=group_id,
                user_id=user_id,
            )
            state = self._persist_inactivity_decay(connection, row)
            now = _utcnow()
            next_score = max(-1.0, min(1.0, score))
            row.score = next_score
            row.last_event_at = now
            row.last_decay_at = None
            self._update_row(connection, row)
            self._record_event(
                connection,
                affinity_id=row.affinity_id,
                platform=row.platform,
                group_id=row.group_id,
                user_id=row.user_id,
                event_type="manual",
                score_delta=next_score - state.score,
                score_after=next_score,
                mood_tag=None,
                reason="manual score override",
                created_at=now,
            )
        return self._to_state(row)

    async def list_states(
        self,
        *,
        limit: int,
    ) -> list[AIRelationshipState]:
        """List recent relationship states for owner-facing management."""
        with database_runtime.connect_sync() as connection:
            rows = connection.execute(
                """
                SELECT
                    id,
                    affinity_id,
                    platform,
                    group_id,
                    scope_key,
                    user_id,
                    score,
                    mood_tags_json,
                    last_event_at,
                    last_decay_at
                FROM ai_affinity
                ORDER BY last_event_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._to_state(_row_to_affinity(row)) for row in rows]

    async def list_events_for_target(
        self,
        *,
        platform: str,
        group_id: str | None,
        user_id: str,
        limit: int,
    ) -> list[AIRelationshipEvent]:
        """List recent events for one relationship target."""
        row = self._find_row(
            platform=platform,
            group_id=group_id,
            user_id=user_id,
        )
        if row is None:
            return []
        return await self.list_events(affinity_id=row.affinity_id, limit=limit)

    async def list_events(
        self,
        *,
        affinity_id: str,
        limit: int,
    ) -> list[AIRelationshipEvent]:
        """List recent persisted events for one affinity state."""
        with database_runtime.connect_sync() as connection:
            rows = connection.execute(
                """
                SELECT
                    id,
                    event_id,
                    affinity_id,
                    platform,
                    group_id,
                    user_id,
                    event_type,
                    score_delta,
                    score_after,
                    mood_tag,
                    reason,
                    created_at
                FROM ai_relationship_event
                WHERE affinity_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (affinity_id, limit),
            ).fetchall()
        return [self._to_event(_row_to_relationship_event(row)) for row in rows]

    async def project_state(
        self,
        *,
        platform: str,
        group_id: str | None,
        user_id: str,
    ) -> EmotionProjection:
        """Build the current emotion projection for one user within a scene."""
        row = self._find_row(
            platform=platform,
            group_id=group_id,
            user_id=user_id,
        )
        if row is None:
            return project_emotion(
                self._build_default_state(
                    platform=platform,
                    group_id=group_id,
                    user_id=user_id,
                )
            )
        return project_emotion(self._build_effective_state(row))

    def _find_row(
        self,
        *,
        platform: str,
        group_id: str | None,
        user_id: str,
    ) -> _AffinityRow | None:
        with database_runtime.connect_sync() as connection:
            return self._find_row_with_connection(
                connection,
                platform=platform,
                group_id=group_id,
                user_id=user_id,
            )

    def _get_or_create_row(
        self,
        connection: "Connection",
        *,
        platform: str,
        group_id: str | None,
        user_id: str,
    ) -> _AffinityRow:
        row = self._find_row_with_connection(
            connection,
            platform=platform,
            group_id=group_id,
            user_id=user_id,
        )
        if row is not None:
            return row

        scope_key = build_affinity_scope_key(group_id)
        now = _utcnow()
        connection.execute(
            """
            INSERT INTO ai_affinity (
                affinity_id,
                platform,
                group_id,
                scope_key,
                user_id,
                score,
                mood_tags_json,
                last_event_at,
                last_decay_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(platform, scope_key, user_id) DO NOTHING
            """,
            (
                f"aff_{uuid4().hex}",
                platform,
                group_id,
                scope_key,
                user_id,
                0.0,
                "[]",
                _datetime_to_text(now),
                None,
            ),
        )
        row = self._find_row_with_connection(
            connection,
            platform=platform,
            group_id=group_id,
            user_id=user_id,
        )
        assert row is not None
        return row

    @staticmethod
    def _find_row_with_connection(
        connection: "Connection",
        *,
        platform: str,
        group_id: str | None,
        user_id: str,
    ) -> _AffinityRow | None:
        scope_key = build_affinity_scope_key(group_id)
        row = connection.execute(
            """
            SELECT
                id,
                affinity_id,
                platform,
                group_id,
                scope_key,
                user_id,
                score,
                mood_tags_json,
                last_event_at,
                last_decay_at
            FROM ai_affinity
            WHERE platform = ? AND scope_key = ? AND user_id = ?
            """,
            (platform, scope_key, user_id),
        ).fetchone()
        return None if row is None else _row_to_affinity(row)

    def _persist_inactivity_decay(
        self,
        connection: "Connection",
        row: _AffinityRow,
    ) -> AIRelationshipState:
        state = self._to_state(row)
        decayed = self._build_effective_state(row)
        if (
            decayed.score == state.score
            and decayed.mood_tags == state.mood_tags
            and decayed.last_decay_at == state.last_decay_at
        ):
            return state

        row.score = decayed.score
        row.mood_tags_json = self._serialize_mood_tags(decayed.mood_tags)
        row.last_decay_at = decayed.last_decay_at
        self._update_row(connection, row)
        self._record_event(
            connection,
            affinity_id=row.affinity_id,
            platform=row.platform,
            group_id=row.group_id,
            user_id=row.user_id,
            event_type="absence_decay",
            score_delta=decayed.score - state.score,
            score_after=decayed.score,
            mood_tag=(decayed.mood_tags[-1] if decayed.mood_tags else None),
            reason="relationship drifted toward neutral after inactivity",
            created_at=row.last_decay_at or _utcnow(),
        )
        return decayed

    @staticmethod
    def _update_row(connection: "Connection", row: _AffinityRow) -> None:
        connection.execute(
            """
            UPDATE ai_affinity
            SET
                score = ?,
                mood_tags_json = ?,
                last_event_at = ?,
                last_decay_at = ?
            WHERE affinity_id = ?
            """,
            (
                row.score,
                row.mood_tags_json,
                _datetime_to_text(row.last_event_at),
                _datetime_to_text(row.last_decay_at),
                row.affinity_id,
            ),
        )

    @staticmethod
    def _record_event(  # noqa: PLR0913
        connection: "Connection",
        *,
        affinity_id: str,
        platform: str,
        group_id: str | None,
        user_id: str,
        event_type: AIRelationshipEventType,
        score_delta: float,
        score_after: float,
        mood_tag: str | None,
        reason: str | None,
        created_at: datetime,
    ) -> None:
        connection.execute(
            """
            INSERT INTO ai_relationship_event (
                event_id,
                affinity_id,
                platform,
                group_id,
                user_id,
                event_type,
                score_delta,
                score_after,
                mood_tag,
                reason,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"rel_evt_{uuid4().hex}",
                affinity_id,
                platform,
                group_id,
                user_id,
                event_type,
                score_delta,
                score_after,
                mood_tag,
                reason,
                _datetime_to_text(created_at),
            ),
        )

    @staticmethod
    def _serialize_mood_tags(mood_tags: tuple[str, ...]) -> str:
        return json.dumps(mood_tags, ensure_ascii=False)

    @staticmethod
    def _build_effective_state(row: _AffinityRow) -> AIRelationshipState:
        state = AIRelationshipService._to_state(row)
        return apply_inactivity_decay(
            state,
            current_time=_utcnow(),
        )

    @staticmethod
    def _build_default_state(
        *,
        platform: str,
        group_id: str | None,
        user_id: str,
    ) -> AIRelationshipState:
        scope_key = build_affinity_scope_key(group_id)
        identity = "|".join((platform, scope_key, user_id))
        return AIRelationshipState(
            affinity_id=(
                "aff_transient_"
                + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
            ),
            platform=platform,
            group_id=group_id,
            user_id=user_id,
            score=0.0,
            mood_tags=(),
            last_event_at=None,
            last_decay_at=None,
        )

    @staticmethod
    def _to_state(row: _AffinityRow) -> AIRelationshipState:
        mood_tags = _deserialize_mood_tags(row.mood_tags_json)
        return AIRelationshipState(
            affinity_id=row.affinity_id,
            platform=row.platform,
            group_id=row.group_id,
            user_id=row.user_id,
            score=row.score,
            mood_tags=mood_tags,
            last_event_at=row.last_event_at,
            last_decay_at=row.last_decay_at,
        )

    @staticmethod
    def _to_event(row: _RelationshipEventRow) -> AIRelationshipEvent:
        return AIRelationshipEvent(
            event_id=row.event_id,
            affinity_id=row.affinity_id,
            platform=row.platform,
            group_id=row.group_id,
            user_id=row.user_id,
            event_type=cast("AIRelationshipEventType", row.event_type),
            score_delta=row.score_delta,
            score_after=row.score_after,
            mood_tag=row.mood_tag,
            reason=row.reason,
            created_at=row.created_at,
        )


def _deserialize_mood_tags(raw_json: str) -> tuple[str, ...]:
    try:
        parsed = json.loads(raw_json or "[]")
    except json.JSONDecodeError:
        return ()
    if not isinstance(parsed, list):
        return ()
    return tuple(item for item in parsed if isinstance(item, str))


def _row_to_affinity(row: tuple[object, ...]) -> _AffinityRow:
    return _AffinityRow(
        id=int(str(row[0])),
        affinity_id=str(row[1]),
        platform=str(row[2]),
        group_id=str(row[3]) if row[3] is not None else None,
        scope_key=str(row[4]),
        user_id=str(row[5]),
        score=float(str(row[6])),
        mood_tags_json=str(row[7] or "[]"),
        last_event_at=_datetime_from_text(row[8]),
        last_decay_at=_optional_datetime_from_text(row[9]),
    )


def _row_to_relationship_event(row: tuple[object, ...]) -> _RelationshipEventRow:
    return _RelationshipEventRow(
        id=int(str(row[0])),
        event_id=str(row[1]),
        affinity_id=str(row[2]),
        platform=str(row[3]),
        group_id=str(row[4]) if row[4] is not None else None,
        user_id=str(row[5]),
        event_type=str(row[6]),
        score_delta=float(str(row[7])),
        score_after=float(str(row[8])),
        mood_tag=str(row[9]) if row[9] is not None else None,
        reason=str(row[10]) if row[10] is not None else None,
        created_at=_datetime_from_text(row[11]),
    )


ai_relationship_service = AIRelationshipService()
